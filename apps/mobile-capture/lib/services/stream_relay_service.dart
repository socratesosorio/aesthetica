import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';

/// A single garment detection returned by the server.
class GarmentDetection {
  GarmentDetection({
    required this.garmentType,
    required this.attributes,
  });

  final String garmentType;
  final Map<String, dynamic> attributes;

  factory GarmentDetection.fromJson(Map<String, dynamic> json) {
    return GarmentDetection(
      garmentType: json['garment_type'] as String? ?? 'unknown',
      attributes: json['attributes'] as Map<String, dynamic>? ?? {},
    );
  }
}

/// A processed result from the backend for one keyframe.
class StreamResultEvent {
  StreamResultEvent({
    required this.seq,
    required this.garments,
    required this.processingMs,
    required this.stats,
  });

  final int seq;
  final List<GarmentDetection> garments;
  final double processingMs;
  final Map<String, dynamic> stats;

  factory StreamResultEvent.fromJson(Map<String, dynamic> json) {
    final garmentsList = json['garments'] as List<dynamic>? ?? [];
    return StreamResultEvent(
      seq: json['seq'] as int? ?? 0,
      garments: garmentsList
          .map((g) => GarmentDetection.fromJson(g as Map<String, dynamic>))
          .toList(),
      processingMs: (json['processing_ms'] as num?)?.toDouble() ?? 0.0,
      stats: json['stats'] as Map<String, dynamic>? ?? {},
    );
  }
}

/// Lightweight ack received for each frame sent.
class FrameAck {
  FrameAck({
    required this.seq,
    required this.isKeyframe,
    required this.bufferDepth,
  });

  final int seq;
  final bool isKeyframe;
  final int bufferDepth;

  factory FrameAck.fromJson(Map<String, dynamic> json) {
    return FrameAck(
      seq: json['seq'] as int? ?? 0,
      isKeyframe: json['is_keyframe'] as bool? ?? false,
      bufferDepth: json['buffer_depth'] as int? ?? 0,
    );
  }
}

/// Connection states for the stream relay.
enum RelayState { disconnected, connecting, connected, error }

/// Relays DAT video frames from the glasses to the backend over WebSocket
/// and exposes a stream of ML results coming back.
///
/// Usage:
/// ```dart
/// final relay = StreamRelayService(baseUrl: 'ws://127.0.0.1:8000', authToken: 'dev');
/// await relay.connect();
/// datService.frames.listen((jpeg) => relay.sendFrame(jpeg));
/// relay.results.listen((result) => print(result.garments));
/// ```
class StreamRelayService {
  StreamRelayService({
    required this.baseUrl,
    required this.authToken,
    this.targetFps = 10,
    this.autoReconnect = true,
    this.maxReconnectAttempts = 5,
  });

  final String baseUrl;
  final String authToken;

  /// Target FPS to send to backend.  Frames arriving faster than this are
  /// dropped on the client side to avoid overwhelming the connection.
  final int targetFps;

  final bool autoReconnect;
  final int maxReconnectAttempts;

  WebSocket? _ws;
  int _reconnectAttempts = 0;

  final StreamController<StreamResultEvent> _resultController =
      StreamController.broadcast();
  final StreamController<FrameAck> _ackController =
      StreamController.broadcast();
  final StreamController<RelayState> _stateController =
      StreamController.broadcast();
  final StreamController<Map<String, dynamic>> _statsController =
      StreamController.broadcast();

  RelayState _state = RelayState.disconnected;

  DateTime? _lastFrameSent;
  int _framesSent = 0;
  int _framesDropped = 0;

  // ── Public streams ───────────────────────────────────────────────────

  /// ML inference results from the backend.
  Stream<StreamResultEvent> get results => _resultController.stream;

  /// Per-frame acknowledgements from the backend.
  Stream<FrameAck> get acks => _ackController.stream;

  /// Connection state changes.
  Stream<RelayState> get stateChanges => _stateController.stream;

  /// Periodic stats beacons from the server.
  Stream<Map<String, dynamic>> get serverStats => _statsController.stream;

  /// Current connection state.
  RelayState get state => _state;

  /// Number of frames successfully sent this session.
  int get framesSent => _framesSent;

  /// Number of frames dropped due to rate limiting.
  int get framesDropped => _framesDropped;

  // ── Lifecycle ────────────────────────────────────────────────────────

  /// Connect to the backend WebSocket streaming endpoint.
  Future<void> connect() async {
    if (_state == RelayState.connected) return;

    _setState(RelayState.connecting);

    try {
      final wsScheme = baseUrl.startsWith('https') ? 'wss' : 'ws';
      final httpStripped = baseUrl
          .replaceFirst('https://', '')
          .replaceFirst('http://', '');
      final uri = '$wsScheme://$httpStripped/v1/stream?token=$authToken';

      debugPrint('[Relay] Connecting to: $uri');
      _ws = await WebSocket.connect(uri);
      _reconnectAttempts = 0;
      _setState(RelayState.connected);
      debugPrint('[Relay] WebSocket connected successfully.');

      _ws!.listen(
        _onMessage,
        onDone: _onDone,
        onError: (e) {
          debugPrint('[Relay] WebSocket stream error: $e');
          _onError(e);
        },
        cancelOnError: false,
      );
    } catch (e, stack) {
      debugPrint('[Relay] WebSocket connection failed: $e');
      debugPrint('[Relay] Stack: $stack');
      _setState(RelayState.error);
      rethrow;
    }
  }

  /// Disconnect gracefully.
  Future<void> disconnect() async {
    _reconnectAttempts = maxReconnectAttempts; // prevent auto-reconnect
    if (_ws != null) {
      _ws!.add(jsonEncode({'type': 'stop'}));
      await _ws!.close();
      _ws = null;
    }
    _setState(RelayState.disconnected);
  }

  /// Send a single JPEG frame to the backend.
  ///
  /// Frames are rate-limited to [targetFps].  Excess frames are silently
  /// dropped — the DAT stream typically runs at 24-30 fps but the backend
  /// only needs 5-15 fps for fashion analysis.
  void sendFrame(Uint8List jpegBytes) {
    if (_state != RelayState.connected || _ws == null) return;

    final now = DateTime.now();
    final minInterval = Duration(milliseconds: (1000 / targetFps).round());

    if (_lastFrameSent != null &&
        now.difference(_lastFrameSent!) < minInterval) {
      _framesDropped++;
      return;
    }

    _lastFrameSent = now;
    _framesSent++;
    _ws!.add(jpegBytes);
  }

  /// Send a control command (text JSON) to the backend.
  void sendCommand(Map<String, dynamic> command) {
    if (_state != RelayState.connected || _ws == null) return;
    _ws!.add(jsonEncode(command));
  }

  /// Request a stats update from the server.
  void requestStats() {
    sendCommand({'type': 'stats'});
  }

  /// Live-tune keyframe detection parameters.
  void configure({
    double? ssimThreshold,
    double? pixelDiffThreshold,
    double? minIntervalS,
    double? maxIntervalS,
  }) {
    final params = <String, dynamic>{'type': 'configure'};
    if (ssimThreshold != null) params['ssim_threshold'] = ssimThreshold;
    if (pixelDiffThreshold != null) {
      params['pixel_diff_threshold'] = pixelDiffThreshold;
    }
    if (minIntervalS != null) params['min_interval_s'] = minIntervalS;
    if (maxIntervalS != null) params['max_interval_s'] = maxIntervalS;
    sendCommand(params);
  }

  /// Reset counters for a fresh session.
  void resetCounters() {
    _framesSent = 0;
    _framesDropped = 0;
    _lastFrameSent = null;
  }

  /// Release all resources.
  Future<void> dispose() async {
    await disconnect();
    await _resultController.close();
    await _ackController.close();
    await _stateController.close();
    await _statsController.close();
  }

  // ── Private ──────────────────────────────────────────────────────────

  void _setState(RelayState s) {
    _state = s;
    _stateController.add(s);
  }

  void _onMessage(dynamic message) {
    if (message is! String) return;

    try {
      final json = jsonDecode(message) as Map<String, dynamic>;
      final type = json['type'] as String? ?? '';

      switch (type) {
        case 'ack':
          _ackController.add(FrameAck.fromJson(json));
          break;
        case 'result':
          _resultController.add(StreamResultEvent.fromJson(json));
          break;
        case 'stats':
          _statsController.add(json);
          break;
        case 'pong':
          // heartbeat ack — nothing to do
          break;
        case 'error':
          // Server-side error; log but keep connection alive.
          break;
        case 'configured':
          break;
        default:
          break;
      }
    } catch (_) {
      // Malformed JSON — ignore.
    }
  }

  void _onDone() {
    _ws = null;
    if (_state != RelayState.disconnected && autoReconnect) {
      _setState(RelayState.disconnected);
      _scheduleReconnect();
    } else {
      _setState(RelayState.disconnected);
    }
  }

  void _onError(dynamic error) {
    _setState(RelayState.error);
    if (autoReconnect) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= maxReconnectAttempts) return;
    _reconnectAttempts++;
    final delay = Duration(seconds: _reconnectAttempts * 2);
    Future.delayed(delay, () {
      if (_state != RelayState.connected) {
        connect();
      }
    });
  }
}
