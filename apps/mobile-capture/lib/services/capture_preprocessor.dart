import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';
import 'package:image/image.dart' as img;
import 'package:path_provider/path_provider.dart';

class CapturePreprocessor {
  static const double _reticleWidthRatio = 0.55;
  static const double _reticleHeightRatio = 0.70;

  Future<Uint8List> preprocess(Uint8List bytes) async {
    final decoded = img.decodeImage(bytes);
    if (decoded == null) {
      throw Exception('Invalid frame bytes');
    }

    final cropped = _reticleCrop(decoded);
    final resized = _downscale(cropped, maxLongSide: 640);
    final blurred = await _faceBlur(resized);

    return Uint8List.fromList(img.encodeJpg(blurred, quality: 82));
  }

  img.Image _reticleCrop(img.Image source) {
    final cropW = (source.width * _reticleWidthRatio).round();
    final cropH = (source.height * _reticleHeightRatio).round();
    final x = ((source.width - cropW) / 2).round();
    final y = ((source.height - cropH) / 2).round();
    return img.copyCrop(source, x: x, y: y, width: cropW, height: cropH);
  }

  img.Image _downscale(img.Image source, {required int maxLongSide}) {
    final longSide = math.max(source.width, source.height);
    if (longSide <= maxLongSide) {
      return source;
    }

    final scale = maxLongSide / longSide;
    final newW = (source.width * scale).round();
    final newH = (source.height * scale).round();
    return img.copyResize(source, width: newW, height: newH, interpolation: img.Interpolation.average);
  }

  Future<img.Image> _faceBlur(img.Image source) async {
    final tmpDir = await getTemporaryDirectory();
    final path = '${tmpDir.path}/aesthetica_face_blur.jpg';
    final file = File(path);
    await file.writeAsBytes(img.encodeJpg(source, quality: 90), flush: true);

    final detector = FaceDetector(
      options: FaceDetectorOptions(
        performanceMode: FaceDetectorMode.fast,
        enableClassification: false,
        enableContours: false,
      ),
    );

    try {
      final input = InputImage.fromFilePath(path);
      final faces = await detector.processImage(input);

      for (final face in faces) {
        final rect = face.boundingBox;
        final x1 = rect.left.clamp(0, source.width - 1).round();
        final y1 = rect.top.clamp(0, source.height - 1).round();
        final x2 = rect.right.clamp(1, source.width).round();
        final y2 = rect.bottom.clamp(1, source.height).round();

        _pixelate(source, x1, y1, x2 - x1, y2 - y1, block: 10);
      }
      return source;
    } catch (_) {
      return source;
    } finally {
      await detector.close();
    }
  }

  void _pixelate(img.Image image, int x, int y, int w, int h, {int block = 8}) {
    for (int yy = y; yy < y + h; yy += block) {
      for (int xx = x; xx < x + w; xx += block) {
        final sampleX = xx.clamp(0, image.width - 1);
        final sampleY = yy.clamp(0, image.height - 1);
        final c = image.getPixel(sampleX, sampleY);

        for (int by = 0; by < block; by++) {
          for (int bx = 0; bx < block; bx++) {
            final px = xx + bx;
            final py = yy + by;
            if (px < image.width && py < image.height) {
              image.setPixel(px, py, c);
            }
          }
        }
      }
    }
  }
}
