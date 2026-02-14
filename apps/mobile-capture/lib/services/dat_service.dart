import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/services.dart';

/// Abstraction for Meta Wearables DAT camera stream.
///
/// Current MVP trigger is in-app capture button. This interface is designed to
/// extend with physical button callback and volume-button shortcut later.
abstract class DatService {
  Stream<Uint8List> get frames;
  Uint8List? get latestFrame;

  Future<void> initialize();
  Future<void> requestCameraPermission();
  Future<void> startStream({int width = 1280, int height = 720, int fps = 30});
  Future<void> stopStream();
}

class RealDatService implements DatService {
  static const MethodChannel _method = MethodChannel('aesthetica/dat');
  static const EventChannel _events = EventChannel('aesthetica/dat_frames');

  final StreamController<Uint8List> _controller = StreamController.broadcast();
  StreamSubscription<dynamic>? _subscription;
  Uint8List? _latest;

  @override
  Stream<Uint8List> get frames => _controller.stream;

  @override
  Uint8List? get latestFrame => _latest;

  @override
  Future<void> initialize() async {
    await _method.invokeMethod('initializeSdk');
    _subscription = _events.receiveBroadcastStream().listen((event) {
      if (event is Uint8List) {
        _latest = event;
        _controller.add(event);
      } else if (event is List<int>) {
        final bytes = Uint8List.fromList(event);
        _latest = bytes;
        _controller.add(bytes);
      }
    });
  }

  @override
  Future<void> requestCameraPermission() async {
    await _method.invokeMethod('requestCameraPermission');
  }

  @override
  Future<void> startStream({int width = 1280, int height = 720, int fps = 30}) async {
    await _method.invokeMethod('startVideoStream', {
      'width': width,
      'height': height,
      'fps': fps,
    });
  }

  @override
  Future<void> stopStream() async {
    await _method.invokeMethod('stopVideoStream');
    await _subscription?.cancel();
    await _controller.close();
  }
}
