import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../services/dat_service.dart';
import '../services/mock_dat_service.dart';
import '../services/stream_relay_service.dart';
import '../widgets/reticle_overlay.dart';

/// Real-time streaming screen that pipes DAT video frames from the Meta
/// Ray-Ban glasses through the backend ML pipeline and shows live garment
/// detections overlaid on the preview.
class StreamScreen extends StatefulWidget {
  const StreamScreen({super.key});

  @override
  State<StreamScreen> createState() => _StreamScreenState();
}

class _StreamScreenState extends State<StreamScreen>
    with SingleTickerProviderStateMixin {
  // ── services ──────────────────────────────────────────────────────────

  late final DatService _dat;
  late final StreamRelayService _relay;
  late final FlutterTts _tts;

  // ── subscriptions ─────────────────────────────────────────────────────

  StreamSubscription<Uint8List>? _frameSub;
  StreamSubscription<Uint8List>? _photoSub;
  StreamSubscription<StreamResultEvent>? _resultSub;
  StreamSubscription<FrameAck>? _ackSub;
  StreamSubscription<RelayState>? _stateSub;
  StreamSubscription<Map<String, dynamic>>? _serverStatsSub;

  // ── state ─────────────────────────────────────────────────────────────

  Uint8List? _currentFrame;
  Uint8List? _capturedPhoto;
  RelayState _relayState = RelayState.disconnected;
  StreamResultEvent? _latestResult;
  int _ackSeq = 0;
  bool _isKeyframe = false;
  Map<String, dynamic> _serverStats = {};
  bool _audioEnabled = true;
  int _photoCaptureCount = 0;
  bool _showCaptureFlash = false;

  // Throttle TTS so it doesn't talk over itself.
  DateTime _lastSpokenAt = DateTime(2000);
  String _lastSpokenText = '';
  static const Duration _ttsMinInterval = Duration(seconds: 4);

  // Animation for keyframe flash.
  late final AnimationController _flashController;
  late final Animation<double> _flashAnimation;

  // Config.
  static const String _apiBaseUrlOverride =
      String.fromEnvironment('API_BASE_URL', defaultValue: '');
  late final String _defaultApiBaseUrl =
      Platform.isAndroid ? 'http://10.0.2.2:8000' : 'http://127.0.0.1:8000';

  // ── lifecycle ─────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();

    _flashController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _flashAnimation = CurvedAnimation(
      parent: _flashController,
      curve: Curves.easeOut,
    );

    _dat = _buildDatService();

    _tts = FlutterTts();
    _tts.setLanguage('en-US');
    _tts.setSpeechRate(0.5);
    _tts.setPitch(1.0);
    _tts.setVolume(1.0);

    final apiBase = _apiBaseUrlOverride.isNotEmpty
        ? _apiBaseUrlOverride
        : _defaultApiBaseUrl;

    _relay = StreamRelayService(
      baseUrl: apiBase,
      authToken:
          const String.fromEnvironment('API_TOKEN', defaultValue: 'dev'),
      targetFps: 15,
    );

    _start();
  }

  DatService _buildDatService() {
    const useMockOverride =
        bool.fromEnvironment('USE_MOCK_DAT', defaultValue: false);
    final useMock = Platform.isIOS ? useMockOverride : true;
    return useMock ? MockDatService() : RealDatService();
  }

  String _lastError = '';

  Future<void> _start() async {
    try {
      // 1. Initialize DAT.
      debugPrint('[Aesthetica] Initializing DAT SDK...');
      await _dat.initialize();
      debugPrint('[Aesthetica] DAT SDK initialized.');

      debugPrint('[Aesthetica] Requesting camera permission...');
      await _dat.requestCameraPermission();
      debugPrint('[Aesthetica] Camera permission granted.');

      debugPrint('[Aesthetica] Starting DAT stream (1920x1080 @30fps)...');
      await _dat.startStream(width: 1920, height: 1080, fps: 30);
      debugPrint('[Aesthetica] DAT stream started.');

      // 2. Connect relay WebSocket.
      final apiBase = _apiBaseUrlOverride.isNotEmpty
          ? _apiBaseUrlOverride
          : _defaultApiBaseUrl;
      debugPrint('[Aesthetica] Connecting WebSocket relay to $apiBase ...');
      await _relay.connect();
      debugPrint('[Aesthetica] WebSocket relay connected.');

      // 3. Subscribe to DAT frames and forward to relay.
      _frameSub = _dat.frames.listen((bytes) {
        if (!mounted) return;
        setState(() => _currentFrame = bytes);
        _relay.sendFrame(bytes);
      });
      debugPrint('[Aesthetica] Subscribed to DAT frame stream.');

      // 3b. Subscribe to hardware capture button photos.
      _photoSub = _dat.capturedPhotos.listen((bytes) {
        if (!mounted) return;
        debugPrint('[Aesthetica] Photo captured from glasses! ${bytes.length} bytes');
        setState(() {
          _capturedPhoto = bytes;
          _photoCaptureCount++;
          _showCaptureFlash = true;
        });
        // Send the hi-res capture as a keyframe to the backend.
        _relay.sendFrame(bytes);
        // Announce via TTS.
        if (_audioEnabled) {
          _tts.speak('Photo captured');
        }
        // Clear the flash after a short delay.
        Future.delayed(const Duration(milliseconds: 600), () {
          if (mounted) setState(() => _showCaptureFlash = false);
        });
      });
      debugPrint('[Aesthetica] Subscribed to photo capture stream.');

      // 4. Subscribe to relay events.
      _resultSub = _relay.results.listen((result) {
        if (!mounted) return;
        setState(() => _latestResult = result);
        _announceDetections(result);
      });

      _ackSub = _relay.acks.listen((ack) {
        if (!mounted) return;
        setState(() {
          _ackSeq = ack.seq;
          _isKeyframe = ack.isKeyframe;
        });
        if (ack.isKeyframe) {
          _flashController.forward(from: 0.0);
        }
      });

      _stateSub = _relay.stateChanges.listen((state) {
        if (!mounted) return;
        debugPrint('[Aesthetica] Relay state changed: $state');
        setState(() => _relayState = state);
      });

      _serverStatsSub = _relay.serverStats.listen((stats) {
        if (!mounted) return;
        setState(() => _serverStats = stats);
      });
    } catch (e, stack) {
      debugPrint('[Aesthetica] ERROR during startup: $e');
      debugPrint('[Aesthetica] Stack trace:\n$stack');
      if (!mounted) return;
      setState(() {
        _relayState = RelayState.error;
        _lastError = e.toString();
      });
    }
  }

  /// Build a natural-language description and speak it via TTS.
  void _announceDetections(StreamResultEvent result) {
    if (!_audioEnabled || result.garments.isEmpty) return;

    final now = DateTime.now();
    if (now.difference(_lastSpokenAt) < _ttsMinInterval) return;

    final descriptions = result.garments.map((g) {
      final parts = <String>[];
      final attrs = g.attributes;
      if (attrs['color'] != null) parts.add(attrs['color'].toString());
      if (attrs['pattern'] != null) parts.add(attrs['pattern'].toString());
      if (attrs['material'] != null) parts.add(attrs['material'].toString());
      if (attrs['brand'] != null) parts.add(attrs['brand'].toString());
      parts.add(g.garmentType);
      return parts.join(' ');
    }).toList();

    final text = descriptions.length == 1
        ? 'I see a ${descriptions.first}'
        : 'I see ${descriptions.join(' and a ')}';

    // Don't repeat the exact same announcement.
    if (text == _lastSpokenText) return;

    _lastSpokenAt = now;
    _lastSpokenText = text;
    _tts.speak(text);
  }

  @override
  void dispose() {
    _frameSub?.cancel();
    _photoSub?.cancel();
    _resultSub?.cancel();
    _ackSub?.cancel();
    _stateSub?.cancel();
    _serverStatsSub?.cancel();
    _tts.stop();
    _dat.stopStream();
    _relay.dispose();
    _flashController.dispose();
    super.dispose();
  }

  // ── build ─────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (_relayState) {
      RelayState.connected => const Color(0xFF3CE37D),
      RelayState.connecting => const Color(0xFFF5B342),
      RelayState.error => const Color(0xFFE5484D),
      RelayState.disconnected => const Color(0xFF888888),
    };

    final statusLabel = switch (_relayState) {
      RelayState.connected => 'Streaming',
      RelayState.connecting => 'Connecting...',
      RelayState.error => _lastError.isNotEmpty
          ? 'Error: $_lastError'
          : 'Connection Error',
      RelayState.disconnected => 'Disconnected',
    };

    return Scaffold(
      backgroundColor: const Color(0xFF0D1414),
      body: SafeArea(
        child: Column(
          children: [
            // ── header ──────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: statusColor,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    statusLabel,
                    style: TextStyle(
                      color: statusColor,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                    ),
                  ),
                  const Spacer(),
                  const Text(
                    'Aesthetica Live',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFFFAF7EF),
                    ),
                  ),
                  const Spacer(),
                  // Frame counter.
                  Text(
                    '#$_ackSeq',
                    style: const TextStyle(
                      color: Color(0xFFAFA79A),
                      fontSize: 12,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ),
            ),

            // ── video preview ───────────────────────────────────────
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  // Background.
                  Container(color: const Color(0xFF111A1A)),

                  // DAT frame preview.
                  if (_currentFrame != null)
                    Image.memory(
                      _currentFrame!,
                      fit: BoxFit.cover,
                      gaplessPlayback: true,
                    ),

                  // Reticle overlay.
                  const ReticleOverlay(),

                  // Keyframe flash indicator.
                  AnimatedBuilder(
                    animation: _flashAnimation,
                    builder: (context, child) {
                      return IgnorePointer(
                        child: Container(
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: const Color(0xFF3CE37D)
                                  .withOpacity(_flashAnimation.value * 0.6),
                              width: 4,
                            ),
                          ),
                        ),
                      );
                    },
                  ),

                  // Capture flash overlay.
                  if (_showCaptureFlash)
                    Positioned.fill(
                      child: IgnorePointer(
                        child: AnimatedOpacity(
                          opacity: _showCaptureFlash ? 0.7 : 0.0,
                          duration: const Duration(milliseconds: 150),
                          child: Container(color: Colors.white),
                        ),
                      ),
                    ),

                  // Garment detection chips.
                  if (_latestResult != null &&
                      _latestResult!.garments.isNotEmpty)
                    Positioned(
                      top: 12,
                      left: 12,
                      right: 12,
                      child: Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: _latestResult!.garments.map((g) {
                          return _GarmentChip(
                            garmentType: g.garmentType,
                            attributes: g.attributes,
                          );
                        }).toList(),
                      ),
                    ),
                ],
              ),
            ),

            // ── stats bar ───────────────────────────────────────────
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              color: const Color(0xFF141E1E),
              child: Column(
                children: [
                  // Server stats row.
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      _StatTile(
                        label: 'FPS',
                        value: _serverStats['effective_fps']?.toString() ??
                            '—',
                      ),
                      _StatTile(
                        label: 'Keyframes',
                        value:
                            _serverStats['keyframes_detected']?.toString() ??
                                '0',
                      ),
                      _StatTile(
                        label: 'Processing',
                        value: _serverStats['avg_processing_ms'] != null
                            ? '${_serverStats['avg_processing_ms']}ms'
                            : '—',
                      ),
                      _StatTile(
                        label: 'Sent',
                        value: '${_relay.framesSent}',
                      ),
                      _StatTile(
                        label: 'Photos',
                        value: '$_photoCaptureCount',
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),

                  // Latest inference summary.
                  if (_latestResult != null)
                    Text(
                      _latestResult!.garments.isEmpty
                          ? 'No garments detected'
                          : 'Detected: ${_latestResult!.garments.map((g) => g.garmentType).join(', ')}',
                      style: const TextStyle(
                        color: Color(0xFFE3DBD0),
                        fontSize: 13,
                      ),
                    ),

                  const SizedBox(height: 8),

                  // Control buttons.
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _ControlButton(
                        icon: _relayState == RelayState.connected
                            ? Icons.stop_circle_outlined
                            : Icons.play_circle_outline,
                        label: _relayState == RelayState.connected
                            ? 'Stop'
                            : 'Start',
                        onTap: () async {
                          if (_relayState == RelayState.connected) {
                            await _relay.disconnect();
                          } else {
                            _relay.resetCounters();
                            await _relay.connect();
                          }
                        },
                      ),
                      const SizedBox(width: 24),
                      _ControlButton(
                        icon: Icons.camera_alt,
                        label: 'Capture',
                        onTap: () async {
                          debugPrint('[Aesthetica] Manual capture button pressed');
                          try {
                            await _dat.capturePhoto();
                            debugPrint('[Aesthetica] capturePhoto() called successfully');
                          } catch (e) {
                            debugPrint('[Aesthetica] capturePhoto() error: $e');
                          }
                        },
                      ),
                      const SizedBox(width: 24),
                      _ControlButton(
                        icon: _audioEnabled
                            ? Icons.volume_up
                            : Icons.volume_off,
                        label: _audioEnabled ? 'Audio On' : 'Audio Off',
                        onTap: () {
                          setState(() => _audioEnabled = !_audioEnabled);
                          if (!_audioEnabled) _tts.stop();
                        },
                      ),
                      const SizedBox(width: 24),
                      _ControlButton(
                        icon: Icons.analytics_outlined,
                        label: 'Stats',
                        onTap: () => _relay.requestStats(),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── helper widgets ────────────────────────────────────────────────────────────

class _GarmentChip extends StatelessWidget {
  const _GarmentChip({
    required this.garmentType,
    required this.attributes,
  });

  final String garmentType;
  final Map<String, dynamic> attributes;

  @override
  Widget build(BuildContext context) {
    final icon = switch (garmentType) {
      'top' => Icons.checkroom,
      'bottom' => Icons.straighten,
      'outerwear' => Icons.dry_cleaning,
      'shoes' => Icons.ice_skating,
      'accessories' => Icons.watch,
      _ => Icons.style,
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF1D2A2B).withOpacity(0.85),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF3CE37D).withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: const Color(0xFF3CE37D)),
          const SizedBox(width: 4),
          Text(
            garmentType.toUpperCase(),
            style: const TextStyle(
              color: Color(0xFFFAF7EF),
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            color: Color(0xFFFAF7EF),
            fontSize: 16,
            fontWeight: FontWeight.w700,
            fontFamily: 'monospace',
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(
            color: Color(0xFFAFA79A),
            fontSize: 10,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

class _ControlButton extends StatelessWidget {
  const _ControlButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Icon(icon, color: const Color(0xFFFAF7EF), size: 28),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: Color(0xFFAFA79A),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}
