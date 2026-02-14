import 'dart:async';

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
    await _method.invokeMethod('initializeSdk');

    _frameSubscription = _frameEvents.receiveBroadcastStream().listen((event) {
      final bytes = _asBytes(event);
      if (bytes == null) return;
      _latest = bytes;
      _frameController.add(bytes);
    });

    _photoSubscription = _photoEvents.receiveBroadcastStream().listen((event) {
      final bytes = _asBytes(event);
      if (bytes == null) return;
      _photoController.add(bytes);
    });
  }

  @override
  Future<void> requestCameraPermission() async {
    await _method.invokeMethod('requestCameraPermission');
  }

  @override
  Future<void> startStream(
      {int width = 1280, int height = 720, int fps = 30}) async {
    await _method.invokeMethod('startVideoStream', {
      'width': width,
      'height': height,
      'fps': fps,
    });
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
