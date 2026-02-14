import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../models/capture_state.dart';
import '../services/api_client.dart';
import '../services/capture_preprocessor.dart';
import '../services/dat_service.dart';
import '../services/mock_dat_service.dart';
import '../widgets/reticle_overlay.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  late final DatService _dat;
  final _pre = CapturePreprocessor();

  StreamSubscription<Uint8List>? _frameSub;
  StreamSubscription<Uint8List>? _photoSub;
  Uint8List? _frame;

  CaptureState _state = CaptureState.idle;
  String _status = 'Ready';
  bool _uploadInFlight = false;

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
    _dat = _buildDatService();
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
      setState(() {
        _status = 'Initializing DAT...';
      });

      await _dat.initialize();
      await _dat.requestCameraPermission();
      await _dat.startStream(width: 1280, height: 720, fps: 24);

      _frameSub = _dat.frames.listen((bytes) {
        setState(() {
          _frame = bytes;
          if (_state == CaptureState.idle && !_uploadInFlight) {
            _status = 'Connected';
          }
        });
      });

      _photoSub = _dat.capturedPhotos.listen((photoBytes) {
        _handleCapturedPhoto(photoBytes, source: 'glasses');
      });

      setState(() {
        _status = 'Connected (hardware button ready)';
      });
    } catch (e) {
      setState(() {
        _state = CaptureState.error;
        _status = 'DAT connection error: $e';
      });
    }
  }

  Future<void> _handleCapturedPhoto(Uint8List photoBytes,
      {required String source}) async {
    if (_uploadInFlight) {
      return;
    }

    _uploadInFlight = true;
    if (mounted) {
      setState(() {
        _state = CaptureState.capturing;
        _status = 'Captured from $source';
      });
    }

    try {
      final processed = await _pre.preprocess(photoBytes);
      if (mounted) {
        setState(() {
          _state = CaptureState.captured;
          _status = 'Processed';
        });
      }

      if (mounted) {
        setState(() {
          _state = CaptureState.sending;
          _status = 'Sending...';
        });
      }

      final captureId = await _api.uploadCapture(processed);
      if (mounted) {
        setState(() {
          _state = CaptureState.sent;
          _status = 'Sent: $captureId';
        });
      }

      await Future<void>.delayed(const Duration(milliseconds: 900));
      if (!mounted) return;
      setState(() {
        _state = CaptureState.idle;
        _status = 'Connected (hardware button ready)';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _state = CaptureState.error;
        _status = 'Capture failed: $e';
      });
    } finally {
      _uploadInFlight = false;
    }
  }

  Future<void> _triggerCapture() async {
    if (_uploadInFlight) {
      return;
    }

    try {
      setState(() {
        _state = CaptureState.capturing;
        _status = 'Triggering glasses capture...';
      });
      await _dat.capturePhoto();
      setState(() {
        _status = 'Waiting for photo...';
      });
    } catch (_) {
      // If provider doesn't support remote capture, fallback to current frame.
      final frame = _dat.latestFrame;
      if (frame == null) {
        setState(() {
          _state = CaptureState.error;
          _status = 'No frame available yet';
        });
        return;
      }
      await _handleCapturedPhoto(frame, source: 'fallback');
    }
  }

  @override
  void dispose() {
    _frameSub?.cancel();
    _photoSub?.cancel();
    _dat.stopStream();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ringColor = switch (_state) {
      CaptureState.sent => const Color(0xFF3CE37D),
      CaptureState.error => const Color(0xFFE5484D),
      CaptureState.sending => const Color(0xFFF5B342),
      _ => const Color(0xFFFAF7EF),
    };

    return Scaffold(
      backgroundColor: const Color(0xFF0D1414),
      body: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.all(12),
              child: Text(
                'Aesthetica Capture',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFFFAF7EF),
                ),
              ),
            ),
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Container(color: const Color(0xFF111A1A)),
                  if (_frame != null)
                    Image.memory(
                      _frame!,
                      fit: BoxFit.cover,
                      gaplessPlayback: true,
                    ),
                  const ReticleOverlay(),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
              child: Column(
                children: [
                  Text(
                    _status,
                    style: const TextStyle(color: Color(0xFFE3DBD0)),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Press glasses camera button or tap below',
                    style: TextStyle(color: Color(0xFFAFA79A), fontSize: 12),
                  ),
                  const SizedBox(height: 12),
                  GestureDetector(
                    onTap:
                        _state == CaptureState.sending ? null : _triggerCapture,
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 220),
                      width: 88,
                      height: 88,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: ringColor, width: 6),
                        color: const Color(0xFF1D2A2B),
                      ),
                    ),
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
