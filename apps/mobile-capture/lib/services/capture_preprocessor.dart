import 'dart:math' as math;
import 'dart:typed_data';

import 'package:image/image.dart' as img;

/// Preprocesses captured frames: reticle crop, downscale, JPEG encode.
///
/// Face blur is handled server-side by `blur_faces_safety()` in the ML
/// pipeline, so we skip it here to avoid the google_mlkit_face_detection
/// native dependency (which is incompatible with Xcode 26 beta).
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

    return Uint8List.fromList(img.encodeJpg(resized, quality: 82));
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
    return img.copyResize(source,
        width: newW, height: newH, interpolation: img.Interpolation.average);
  }
}
