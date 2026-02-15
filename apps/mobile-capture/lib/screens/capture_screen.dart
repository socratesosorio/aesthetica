import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/capture_state.dart';
import '../models/catalog_result.dart';
import '../services/api_client.dart';
import '../services/capture_preprocessor.dart';
import '../services/dat_service.dart';
import '../services/mock_dat_service.dart';
import '../services/snap_detector_service.dart';
import '../widgets/glass_container.dart';
import '../widgets/reticle_overlay.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  late final DatService _dat;
  late final FlutterTts _tts;
  late final SnapDetectorService _snapDetector;
  final _pre = CapturePreprocessor();

  StreamSubscription<Uint8List>? _frameSub;
  StreamSubscription<Uint8List>? _photoSub;
  Uint8List? _frame;

  CaptureState _state = CaptureState.idle;
  String _status = 'Ready';
  bool _uploadInFlight = false;
  bool _snapEnabled = true;
  bool _isRecording = false;
  bool _isPlaying = false;
  String? _lastRecordingPath;
  int _captureCount = 0;

  /// Latest catalog result from the API.
  CatalogResult? _catalogResult;
  bool _showResults = false;

  // In production, this token comes from login/session flow.
  static const String _apiBaseUrlOverride =
      String.fromEnvironment('API_BASE_URL', defaultValue: '');
  late final String _defaultApiBaseUrl =
      Platform.isAndroid ? 'http://10.0.2.2:8000' : 'http://127.0.0.1:8000';
  late final CaptureApiClient _api = CaptureApiClient(
    baseUrl: _apiBaseUrlOverride.isNotEmpty
        ? _apiBaseUrlOverride
        : _defaultApiBaseUrl,
    authToken: const String.fromEnvironment('API_TOKEN', defaultValue: 'dev'),
  );

  @override
  void initState() {
    super.initState();
    debugPrint('[Capture] initState()');
    _dat = _buildDatService();

    _tts = FlutterTts();
    _tts.setLanguage('en-US');
    _tts.setSpeechRate(0.5);
    _tts.setVolume(1.0);

    _snapDetector = SnapDetectorService(
      requireDoubleSnap: true,
      cooldownMs: 2000,
      onSnap: _onSnapDetected,
    );

    _start();
  }

  DatService _buildDatService() {
    // On iOS, default to native DAT bridge. On non-iOS, keep mock default.
    const useMockOverride =
        bool.fromEnvironment('USE_MOCK_DAT', defaultValue: false);
    final useMock = Platform.isIOS ? useMockOverride : true;
    return useMock ? MockDatService() : RealDatService();
  }

  Future<void> _start() async {
    try {
      debugPrint('[Capture] ── Starting capture flow ──');
      setState(() {
        _status = 'Initializing DAT...';
      });

      debugPrint('[Capture] Initializing DAT SDK...');
      await _dat.initialize();
      debugPrint('[Capture] DAT SDK initialized.');

      debugPrint('[Capture] Requesting camera permission...');
      await _dat.requestCameraPermission();
      debugPrint('[Capture] Camera permission granted.');

      debugPrint('[Capture] Starting DAT stream (2592x1944 @60fps)...');
      await _dat.startStream(width: 2592, height: 1944, fps: 60);
      debugPrint('[Capture] DAT stream started.');

      _frameSub = _dat.frames.listen((bytes) {
        if (!mounted) return;
        setState(() {
          _frame = bytes;
          if (_state == CaptureState.idle && !_uploadInFlight) {
            _status = 'Connected';
          }
        });
      });
      debugPrint('[Capture] Subscribed to frame stream.');

      _photoSub = _dat.capturedPhotos.listen((photoBytes) {
        debugPrint('[Capture] Photo received from glasses! '
            '${photoBytes.length} bytes');
        _handleCapturedPhoto(photoBytes, source: 'glasses');
      });
      debugPrint('[Capture] Subscribed to photo capture stream.');

      // Start snap detector (uses glasses Bluetooth HFP mic).
      debugPrint('[Capture] Snap detector enabled=$_snapEnabled');
      if (_snapEnabled) {
        try {
          debugPrint('[Capture] Starting snap detector...');
          await _snapDetector.start();
          debugPrint('[Capture] ✓ Snap detector started. '
              'isRunning=${_snapDetector.isRunning}');
        } catch (e, stack) {
          debugPrint('[Capture] ✗ Snap detector failed to start: $e');
          debugPrint('[Capture] Stack: $stack');
        }
      }

      setState(() {
        _status = _snapEnabled
            ? 'Connected (snap to capture)'
            : 'Connected (hardware button ready)';
      });
      debugPrint('[Capture] ── Startup complete ──');
    } catch (e, stack) {
      debugPrint('[Capture] ✗ ERROR during startup: $e');
      debugPrint('[Capture] Stack: $stack');
      setState(() {
        _state = CaptureState.error;
        _status = 'DAT connection error: $e';
      });
    }
  }

  /// Called when the snap detector fires (double finger snap on glasses mic).
  void _onSnapDetected() {
    final ts = DateTime.now().toIso8601String();
    debugPrint('[Capture][$ts] ★ SNAP DETECTED callback fired! '
        'mounted=$mounted, uploadInFlight=$_uploadInFlight, '
        'captureCount=$_captureCount');

    if (!mounted) {
      debugPrint('[Capture] Ignoring snap — widget not mounted.');
      return;
    }

    _captureCount++;
    _tts.speak('Snap captured');
    debugPrint('[Capture] TTS: "Snap captured", triggering capture...');

    // Trigger the same flow as the glasses button / manual capture.
    _triggerCapture();
  }

  Future<void> _handleCapturedPhoto(Uint8List photoBytes,
      {required String source}) async {
    debugPrint('[Capture] _handleCapturedPhoto: source=$source, '
        'size=${photoBytes.length} bytes, uploadInFlight=$_uploadInFlight');

    if (_uploadInFlight) {
      debugPrint('[Capture] Skipping — upload already in flight.');
      return;
    }

    _uploadInFlight = true;
    _captureCount++;
    if (mounted) {
      setState(() {
        _state = CaptureState.capturing;
        _status = 'Captured from $source (#$_captureCount)';
        _showResults = false;
        _catalogResult = null;
      });
    }

    try {
      debugPrint('[Capture] Preprocessing photo...');
      final processed = await _pre.preprocess(photoBytes);
      debugPrint('[Capture] Preprocessing done. '
          'Processed size=${processed.length} bytes');
      if (mounted) {
        setState(() {
          _state = CaptureState.captured;
          _status = 'Processed';
        });
      }

      if (mounted) {
        setState(() {
          _state = CaptureState.sending;
          _status = 'Analyzing garment...';
        });
      }

      debugPrint('[Capture] Calling catalog API...');
      final result = await _api.catalogFromImage(processed);
      debugPrint('[Capture] ✓ Catalog response: '
          'status=${result.pipelineStatus}, '
          'garment=${result.garmentName}, '
          'recommendations=${result.recommendations.length}');

      if (mounted) {
        setState(() {
          _catalogResult = result;
          _state = CaptureState.sent;
          if (result.hasResults) {
            _status =
                '${result.garmentName ?? "Garment"} — ${result.recommendations.length} results';
            _showResults = true;
          } else {
            _status = result.error ?? 'No products found';
          }
        });
      }

      // Announce via TTS.
      if (result.hasResults) {
        final first = result.recommendations.first;
        _tts.speak(
            'Found ${result.recommendations.length} results for ${result.garmentName ?? "this garment"}. '
            'Top match: ${first.title}');
      }
    } catch (e) {
      debugPrint('[Capture] ✗ Catalog request failed: $e');
      if (!mounted) return;
      setState(() {
        _state = CaptureState.error;
        _status = 'Catalog failed: $e';
      });
    } finally {
      _uploadInFlight = false;
    }
  }

  Future<void> _triggerCapture() async {
    debugPrint('[Capture] _triggerCapture() called. '
        'uploadInFlight=$_uploadInFlight');
    if (_uploadInFlight) {
      debugPrint('[Capture] Skipping — upload already in flight.');
      return;
    }

    try {
      setState(() {
        _state = CaptureState.capturing;
        _status = 'Triggering glasses capture...';
      });
      debugPrint('[Capture] Calling _dat.capturePhoto()...');
      await _dat.capturePhoto();
      debugPrint(
          '[Capture] ✓ capturePhoto() returned. Waiting for photo data...');
      setState(() {
        _status = 'Waiting for photo...';
      });
    } catch (e) {
      debugPrint('[Capture] capturePhoto() failed: $e — using fallback frame');
      // If provider doesn't support remote capture, fallback to current frame.
      final frame = _dat.latestFrame;
      if (frame == null) {
        debugPrint('[Capture] Fallback failed: no frame available');
        setState(() {
          _state = CaptureState.error;
          _status = 'No frame available yet';
        });
        return;
      }
      debugPrint('[Capture] Using fallback frame: ${frame.length} bytes');
      await _handleCapturedPhoto(frame, source: 'fallback');
    }
  }

  Future<void> _playRecording() async {
    final path = _lastRecordingPath;
    if (path == null) return;

    if (_isPlaying) {
      debugPrint('[Capture] Stopping playback...');
      await _snapDetector.stopPlayback();
      setState(() => _isPlaying = false);
      return;
    }

    debugPrint('[Capture] Playing recording: $path');
    setState(() => _isPlaying = true);

    try {
      await _snapDetector.playRecording(path);
      Future.delayed(const Duration(seconds: 3), () {
        if (mounted && _isPlaying) {
          setState(() => _isPlaying = false);
        }
      });
    } catch (e) {
      debugPrint('[Capture] Playback error: $e');
      if (mounted) setState(() => _isPlaying = false);
    }
  }

  Widget _buildRecordPlayButton() {
    if (_isRecording) {
      return GlassIconButton(
        icon: Icons.stop_circle,
        label: 'Stop Rec',
        iconColor: const Color(0xFFE5484D),
        onTap: () async {
          debugPrint('[Capture] Stopping audio recording...');
          final path = await _snapDetector.stopRecording();
          setState(() {
            _isRecording = false;
            _lastRecordingPath = path;
          });
          if (path != null) {
            debugPrint('[Capture] Recording saved: $path');
          }
        },
      );
    }

    if (_lastRecordingPath != null) {
      return GlassIconButton(
        icon: _isPlaying ? Icons.stop : Icons.play_arrow,
        label: _isPlaying ? 'Stop' : 'Play',
        isActive: true,
        activeColor: const Color(0xFF3CE37D),
        onTap: _isPlaying
            ? () {
                _snapDetector.stopPlayback();
                setState(() => _isPlaying = false);
              }
            : _playRecording,
      );
    }

    return GlassIconButton(
      icon: Icons.fiber_manual_record,
      label: 'Record',
      onTap: () {
        debugPrint('[Capture] Starting audio recording...');
        _snapDetector.startRecording();
        setState(() => _isRecording = true);
      },
    );
  }

  @override
  void dispose() {
    debugPrint('[Capture] dispose() — cleaning up');
    _frameSub?.cancel();
    _photoSub?.cancel();
    _tts.stop();
    _snapDetector.stopPlayback();
    _snapDetector.dispose();
    _dat.stopStream();
    super.dispose();
  }

  // ── build ─────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final ringColor = switch (_state) {
      CaptureState.sent => const Color(0xFF3CE37D),
      CaptureState.error => const Color(0xFFE5484D),
      CaptureState.sending => const Color(0xFFF5B342),
      _ => const Color(0xFFF0EDE5),
    };

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: AestheticaBackground(
        child: Stack(
          children: [
            // Background glow orbs.
            const GlowOrb(
              color: Color(0xFF1A6B5C),
              size: 250,
              alignment: Alignment(-1.0, -0.6),
              opacity: 0.08,
            ),
            const GlowOrb(
              color: Color(0xFF6B4A1A),
              size: 180,
              alignment: Alignment(1.0, 0.8),
              opacity: 0.06,
            ),

            SafeArea(
              child: Column(
                children: [
                  // ─── Header ────────────────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    child: Row(
                      children: [
                        GestureDetector(
                          onTap: () => Navigator.maybePop(context),
                          child: ClipOval(
                            child: BackdropFilter(
                              filter: ImageFilter.blur(
                                  sigmaX: 10, sigmaY: 10),
                              child: Container(
                                width: 36,
                                height: 36,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: Colors.white.withOpacity(0.06),
                                  border: Border.all(
                                    color: Colors.white.withOpacity(0.1),
                                  ),
                                ),
                                child: Icon(
                                  Icons.arrow_back_ios_new,
                                  size: 14,
                                  color: Colors.white.withOpacity(0.7),
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        const Text(
                          'CAPTURE',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w300,
                            color: Color(0xFFF0EDE5),
                            letterSpacing: 3.0,
                          ),
                        ),
                        const Spacer(),
                        if (_captureCount > 0)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(12),
                              color: const Color(0xFF3CE37D)
                                  .withOpacity(0.12),
                              border: Border.all(
                                color: const Color(0xFF3CE37D)
                                    .withOpacity(0.2),
                              ),
                            ),
                            child: Text(
                              '$_captureCount',
                              style: const TextStyle(
                                color: Color(0xFF3CE37D),
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                fontFamily: 'monospace',
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),

                  // ─── Video preview ─────────────────────────
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 4),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(20),
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            Container(
                              decoration: BoxDecoration(
                                color: const Color(0xFF0A1214),
                                borderRadius: BorderRadius.circular(20),
                              ),
                            ),
                            if (_frame != null)
                              Image.memory(
                                _frame!,
                                fit: BoxFit.cover,
                                gaplessPlayback: true,
                              ),
                            const ReticleOverlay(),
                            // Subtle inner glass border.
                            Positioned.fill(
                              child: IgnorePointer(
                                child: Container(
                                  decoration: BoxDecoration(
                                    borderRadius:
                                        BorderRadius.circular(20),
                                    border: Border.all(
                                      color:
                                          Colors.white.withOpacity(0.08),
                                      width: 1,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 6),

                  // ─── Status text ───────────────────────────
                  Text(
                    _status,
                    style: TextStyle(
                      color: const Color(0xFFE3DBD0).withOpacity(0.8),
                      fontSize: 12,
                      fontWeight: FontWeight.w300,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _snapEnabled
                        ? 'Double-snap your fingers or tap below'
                        : 'Press glasses camera button or tap below',
                    style: TextStyle(
                      color: const Color(0xFFAFA79A).withOpacity(0.5),
                      fontSize: 11,
                      fontWeight: FontWeight.w300,
                    ),
                  ),
                  const SizedBox(height: 10),

                  // ─── Bottom controls panel ─────────────────
                  GlassContainer(
                    margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                    padding:
                        const EdgeInsets.fromLTRB(16, 16, 16, 20),
                    borderRadius: 28,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        // Snap toggle.
                        GlassIconButton(
                          icon: _snapEnabled
                              ? Icons.sensors
                              : Icons.sensors_off,
                          label:
                              _snapEnabled ? 'Snap On' : 'Snap Off',
                          isActive: _snapEnabled,
                          activeColor: const Color(0xFF3CE37D),
                          onTap: () async {
                            if (_snapEnabled) {
                              debugPrint(
                                  '[Capture] User toggling snap OFF...');
                              await _snapDetector.stop();
                              setState(() => _snapEnabled = false);
                              debugPrint(
                                  '[Capture] Snap detector stopped.');
                            } else {
                              debugPrint(
                                  '[Capture] User toggling snap ON...');
                              try {
                                await _snapDetector.start();
                                setState(() => _snapEnabled = true);
                                debugPrint(
                                    '[Capture] Snap detector restarted. '
                                    'isRunning=${_snapDetector.isRunning}');
                              } catch (e) {
                                debugPrint(
                                    '[Capture] Snap detector start error: $e');
                              }
                            }
                          },
                        ),

                        // ─── Capture button with glow ring ───
                        GestureDetector(
                          onTap: _state == CaptureState.sending
                              ? null
                              : _triggerCapture,
                          child: Container(
                            width: 80,
                            height: 80,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: ringColor.withOpacity(0.25),
                                  blurRadius: 28,
                                  spreadRadius: 4,
                                ),
                              ],
                            ),
                            child: Container(
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                    color: ringColor, width: 4),
                                color: Colors.white.withOpacity(0.04),
                              ),
                              child: Container(
                                margin: const EdgeInsets.all(6),
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: ringColor.withOpacity(0.15),
                                ),
                              ),
                            ),
                          ),
                        ),

                        // Results / Record button.
                        _catalogResult != null && _catalogResult!.hasResults
                            ? GlassIconButton(
                                icon: Icons.shopping_bag_outlined,
                                label: 'Results',
                                isActive: true,
                                activeColor: const Color(0xFFF5B342),
                                onTap: () =>
                                    setState(() => _showResults = true),
                              )
                            : _buildRecordPlayButton(),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            // ─── Catalog results overlay ───────────────────
            if (_showResults && _catalogResult != null)
              _CatalogResultsOverlay(
                result: _catalogResult!,
                onClose: () => setState(() => _showResults = false),
              ),
          ],
        ),
      ),
    );
  }
}

// ── Catalog results overlay ──────────────────────────────────────────────────

class _CatalogResultsOverlay extends StatelessWidget {
  const _CatalogResultsOverlay({
    required this.result,
    required this.onClose,
  });

  final CatalogResult result;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: GestureDetector(
        onTap: onClose,
        child: Container(
          color: Colors.black.withOpacity(0.4),
          child: SafeArea(
            child: Column(
              children: [
                const Spacer(flex: 1),
                // Results panel.
                Expanded(
                  flex: 4,
                  child: GestureDetector(
                    onTap: () {}, // Prevent tap-through.
                    child: GlassContainer(
                      margin: const EdgeInsets.symmetric(horizontal: 12),
                      padding: const EdgeInsets.fromLTRB(0, 16, 0, 0),
                      borderRadius: 24,
                      blur: 28,
                      opacity: 0.08,
                      borderOpacity: 0.15,
                      child: Column(
                        children: [
                          // Header.
                          Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 16),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        result.garmentName?.toUpperCase() ??
                                            'RESULTS',
                                        style: const TextStyle(
                                          color: Color(0xFFF0EDE5),
                                          fontSize: 14,
                                          fontWeight: FontWeight.w300,
                                          letterSpacing: 2.0,
                                        ),
                                      ),
                                      const SizedBox(height: 2),
                                      if (result.brandHint != null)
                                        Text(
                                          result.brandHint!,
                                          style: TextStyle(
                                            color: const Color(0xFFF5B342)
                                                .withOpacity(0.8),
                                            fontSize: 12,
                                            fontWeight: FontWeight.w500,
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                                if (result.confidence != null)
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      borderRadius:
                                          BorderRadius.circular(10),
                                      color: const Color(0xFF3CE37D)
                                          .withOpacity(0.12),
                                    ),
                                    child: Text(
                                      '${(result.confidence! * 100).toInt()}%',
                                      style: const TextStyle(
                                        color: Color(0xFF3CE37D),
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        fontFamily: 'monospace',
                                      ),
                                    ),
                                  ),
                                const SizedBox(width: 8),
                                GestureDetector(
                                  onTap: onClose,
                                  child: Container(
                                    width: 30,
                                    height: 30,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color:
                                          Colors.white.withOpacity(0.06),
                                    ),
                                    child: Icon(
                                      Icons.close,
                                      size: 16,
                                      color:
                                          Colors.white.withOpacity(0.5),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                          Divider(
                            height: 1,
                            color: Colors.white.withOpacity(0.06),
                          ),
                          // Product list.
                          Expanded(
                            child: ListView.separated(
                              padding: const EdgeInsets.symmetric(
                                  vertical: 8),
                              itemCount:
                                  result.recommendations.length,
                              separatorBuilder: (_, __) => Divider(
                                height: 1,
                                indent: 16,
                                endIndent: 16,
                                color:
                                    Colors.white.withOpacity(0.04),
                              ),
                              itemBuilder: (context, index) {
                                return _ProductTile(
                                  rec: result
                                      .recommendations[index],
                                );
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ProductTile extends StatelessWidget {
  const _ProductTile({required this.rec});

  final CatalogRecommendation rec;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () async {
        final uri = Uri.tryParse(rec.productUrl);
        if (uri != null) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            // Product image.
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Container(
                width: 56,
                height: 56,
                color: Colors.white.withOpacity(0.04),
                child: rec.imageUrl != null
                    ? Image.network(
                        rec.imageUrl!,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Icon(
                          Icons.image_not_supported_outlined,
                          color: Colors.white.withOpacity(0.2),
                          size: 22,
                        ),
                      )
                    : Icon(
                        Icons.shopping_bag_outlined,
                        color: Colors.white.withOpacity(0.2),
                        size: 22,
                      ),
              ),
            ),
            const SizedBox(width: 12),
            // Details.
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    rec.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Color(0xFFF0EDE5),
                      fontSize: 13,
                      fontWeight: FontWeight.w400,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Row(
                    children: [
                      if (rec.source != null)
                        Text(
                          rec.source!,
                          style: TextStyle(
                            color:
                                const Color(0xFFAFA79A).withOpacity(0.7),
                            fontSize: 11,
                          ),
                        ),
                      if (rec.source != null && rec.priceText != null)
                        Text(
                          '  ·  ',
                          style: TextStyle(
                            color:
                                const Color(0xFFAFA79A).withOpacity(0.3),
                            fontSize: 11,
                          ),
                        ),
                      if (rec.priceText != null)
                        Text(
                          rec.priceText!,
                          style: const TextStyle(
                            color: Color(0xFF3CE37D),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              Icons.open_in_new,
              size: 16,
              color: Colors.white.withOpacity(0.3),
            ),
          ],
        ),
      ),
    );
  }
}
