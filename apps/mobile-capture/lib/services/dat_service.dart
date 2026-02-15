import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Abstraction for Meta Wearables DAT camera stream.
///
/// Supports both preview frames and photo capture events.
/// On real DAT integrations, `capturedPhotos` receives photos captured from
/// either in-app `capturePhoto()` calls or glasses hardware camera button events.
abstract class DatService {
  Stream<Uint8List> get frames;
  Stream<Uint8List> get capturedPhotos;
  Uint8List? get latestFrame;

  Future<void> initialize();
  Future<void> requestCameraPermission();
  Future<void> startStream({int width = 1280, int height = 720, int fps = 30});
  Future<void> stopStream();
  Future<void> capturePhoto();
}

class RealDatService implements DatService {
  static const MethodChannel _method = MethodChannel('aesthetica/dat');
  static const EventChannel _frameEvents =
      EventChannel('aesthetica/dat_frames');
  static const EventChannel _photoEvents =
      EventChannel('aesthetica/dat_photo_captures');

  final StreamController<Uint8List> _frameController =
      StreamController.broadcast();
  final StreamController<Uint8List> _photoController =
      StreamController.broadcast();

  StreamSubscription<dynamic>? _frameSubscription;
  StreamSubscription<dynamic>? _photoSubscription;

  Uint8List? _latest;

  @override
  Stream<Uint8List> get frames => _frameController.stream;

  @override
  Stream<Uint8List> get capturedPhotos => _photoController.stream;

  @override
  Uint8List? get latestFrame => _latest;

  @override
  Future<void> initialize() async {
    try {
      debugPrint('[DAT] Calling initializeSdk...');
      await _method.invokeMethod('initializeSdk');
      debugPrint('[DAT] initializeSdk succeeded.');
    } catch (e) {
      debugPrint('[DAT] initializeSdk FAILED: $e');
      rethrow;
    }

    _frameSubscription = _frameEvents.receiveBroadcastStream().listen(
      (event) {
        final bytes = _asBytes(event);
        if (bytes == null) return;
        _latest = bytes;
        _frameController.add(bytes);
      },
      onError: (e) => debugPrint('[DAT] Frame stream error: $e'),
    );

    _photoSubscription = _photoEvents.receiveBroadcastStream().listen(
      (event) {
        final bytes = _asBytes(event);
        if (bytes == null) return;
        _photoController.add(bytes);
      },
      onError: (e) => debugPrint('[DAT] Photo stream error: $e'),
    );
  }

  @override
  Future<void> requestCameraPermission() async {
    try {
      debugPrint('[DAT] Requesting camera permission...');
      await _method.invokeMethod('requestCameraPermission');
      debugPrint('[DAT] Camera permission granted.');
    } catch (e) {
      debugPrint('[DAT] Camera permission FAILED: $e');
      rethrow;
    }
  }

  @override
  Future<void> startStream(
      {int width = 1280, int height = 720, int fps = 30}) async {
    try {
      debugPrint('[DAT] Starting video stream ${width}x$height @${fps}fps...');
      await _method.invokeMethod('startVideoStream', {
        'width': width,
        'height': height,
        'fps': fps,
      });
      debugPrint('[DAT] Video stream started.');
    } catch (e) {
      debugPrint('[DAT] startVideoStream FAILED: $e');
      rethrow;
    }
  }

  @override
  Future<void> stopStream() async {
    await _method.invokeMethod('stopVideoStream');
    await _frameSubscription?.cancel();
    await _photoSubscription?.cancel();
    await _frameController.close();
    await _photoController.close();
  }

  @override
  Future<void> capturePhoto() async {
    await _method.invokeMethod('capturePhoto');
  }

  Uint8List? _asBytes(dynamic event) {
    if (event is Uint8List) return event;
    if (event is List<int>) return Uint8List.fromList(event);
    return null;
  }
}
