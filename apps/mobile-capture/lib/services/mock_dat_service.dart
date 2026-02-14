import 'dart:async';
import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'dat_service.dart';

class MockDatService implements DatService {
  final StreamController<Uint8List> _controller = StreamController.broadcast();
  Timer? _timer;
  Uint8List? _latest;
  int _tick = 0;

  @override
  Stream<Uint8List> get frames => _controller.stream;

  @override
  Uint8List? get latestFrame => _latest;

  @override
  Future<void> initialize() async {}

  @override
  Future<void> requestCameraPermission() async {}

  @override
  Future<void> startStream(
      {int width = 1280, int height = 720, int fps = 30}) async {
    final interval = Duration(milliseconds: (1000 / fps).round());
    _timer = Timer.periodic(interval, (_) {
      final frame = img.Image(width: width, height: height);
      img.fill(frame, color: img.ColorRgb8(20, 24, 34));

      final stripe = (_tick * 12) % width;
      img.fillRect(
        frame,
        x1: stripe,
        y1: 0,
        x2: ((stripe + 120).clamp(0, width) as num).toInt(),
        y2: height,
        color: img.ColorRgb8(245, 179, 66),
      );

      img.drawString(
        frame,
        'MOCK DAT STREAM',
        font: img.arial24,
        x: 28,
        y: 28,
        color: img.ColorRgb8(255, 255, 255),
      );

      _tick += 1;
      final jpg = Uint8List.fromList(img.encodeJpg(frame, quality: 80));
      _latest = jpg;
      _controller.add(jpg);
    });
  }

  @override
  Future<void> stopStream() async {
    _timer?.cancel();
    await _controller.close();
  }
}
