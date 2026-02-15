import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_voice_processor/flutter_voice_processor.dart';
import 'package:path_provider/path_provider.dart';

/// Low-latency finger snap detector tuned for the Meta Ray-Ban glasses
/// Bluetooth HFP microphone.
///
/// Uses a research-backed approach (see: pector, clapDetection) combining:
///   1. Bandpass filter (1–3.5 kHz) — isolates snap energy, attenuates speech.
///   2. Zero Crossing Rate (ZCR) — distinguishes broadband percussive noise
///      (snaps: ZCR > 0.3) from periodic speech (ZCR < 0.2). This is the key
///      feature that separates snaps from voice with 95–97% accuracy.
///   3. Filtered RMS spike — must exceed ambient by N× AND absolute minimum.
///   4. Transient duration — rejects sustained sounds (speech) that stay loud
///      for more than 2 frames (~64ms). Snaps are 1–2 frames max.
///   5. Double-snap pattern + cooldown.
class SnapDetectorService {
  SnapDetectorService({
    this.minFilteredRms = 300.0,
    this.spikeMultiplier = 8.0,
    this.minZcr = 0.20,
    this.maxHotFrames = 2,
    this.requireDoubleSnap = true,
    this.doubleSnapWindowMs = 1500,
    this.doubleSnapMinGapMs = 120,
    this.cooldownMs = 2000,
    VoidCallback? onSnap,
  }) : _onSnap = onSnap;

  // ── Configuration ────────────────────────────────────────────────────

  /// Minimum RMS of the bandpass-filtered signal for a snap candidate.
  double minFilteredRms;

  /// Spike ratio: filtered RMS must exceed ambient by this factor.
  double spikeMultiplier;

  /// Minimum Zero Crossing Rate (0–1) on the bandpass-filtered signal.
  /// Through the 1–3.5kHz bandpass: snaps ~0.23–0.35, speech ~0.10–0.18.
  /// 0.20 gives good separation while catching borderline snaps.
  double minZcr;

  /// Max consecutive hot frames. Snaps: 1–2 frames. Speech: 10–20+.
  int maxHotFrames;

  bool requireDoubleSnap;
  int doubleSnapWindowMs;
  int doubleSnapMinGapMs;
  int cooldownMs;

  // ── Callback ─────────────────────────────────────────────────────────

  VoidCallback? _onSnap;
  set onSnap(VoidCallback? cb) => _onSnap = cb;

  // ── Internal state ───────────────────────────────────────────────────

  static const int _sampleRate = 16000;
  static const int _frameLength = 512;

  VoiceProcessor? _voiceProcessor;
  late final VoiceProcessorFrameListener _frameListener;

  bool _running = false;
  bool get isRunning => _running;

  DateTime _lastTriggerTime = DateTime(2000);
  DateTime _firstSnapTime = DateTime(2000);
  bool _awaitingSecondSnap = false;

  // Rolling ambient (on filtered signal).
  double _ambientRms = 0;
  static const double _ambientAlpha = 0.04;
  bool _ambientInitialized = false;

  // Transient tracking.
  int _consecutiveHotFrames = 0;

  // Bandpass filter state (2nd-order Butterworth, 1–3.5 kHz at 16 kHz).
  // Coefficients computed offline for stability.
  // Butterworth bandpass [1000, 3500] Hz at fs=16000 Hz, order=2
  static const List<double> _bpB = [
    0.1311028, 0.0, -0.2622057, 0.0, 0.1311028
  ];
  static const List<double> _bpA = [
    1.0, -1.5610181, 1.2626890, -0.6584044, 0.2643477
  ];
  // Filter delay line (persistent across frames for continuity).
  final List<double> _bpX = [0, 0, 0, 0]; // x[n-1]..x[n-4]
  final List<double> _bpY = [0, 0, 0, 0]; // y[n-1]..y[n-4]

  // Stats.
  int _totalFrames = 0;
  int _snapsDetected = 0;
  int get snapsDetected => _snapsDetected;

  static const int _logEveryNFrames = 50;
  double _peakRms = 0;
  double _peakZcr = 0;
  double _peakSpikeRatio = 0;
  int _framesPassedSpike = 0;
  int _framesPassedZcr = 0;
  int _framesSustainedRejected = 0;
  int _framesCooldownRejected = 0;
  int _framesEchoRejected = 0;
  int _framesWindowExpired = 0;
  final Stopwatch _uptimeWatch = Stopwatch();

  // ── Audio recording ──────────────────────────────────────────────────

  bool _recording = false;
  bool get isRecording => _recording;
  final List<int> _recordBuffer = [];
  String? _lastRecordingPath;
  String? get lastRecordingPath => _lastRecordingPath;
  static const int _maxRecordSamples = 16000 * 60;

  // ── Platform channel ─────────────────────────────────────────────────

  static const MethodChannel _channel = MethodChannel('aesthetica/dat');

  // ── Public API ───────────────────────────────────────────────────────

  Future<void> start() async {
    if (_running) {
      debugPrint('[SnapDetector] Already running.');
      return;
    }

    debugPrint('[SnapDetector] ── STARTING ──────────────────────────────');
    debugPrint('[SnapDetector] Config: minFilteredRms=$minFilteredRms, '
        'spikeMultiplier=$spikeMultiplier, minZcr=$minZcr, '
        'maxHotFrames=$maxHotFrames');
    debugPrint('[SnapDetector] Config: requireDoubleSnap=$requireDoubleSnap, '
        'doubleSnapWindowMs=$doubleSnapWindowMs, '
        'doubleSnapMinGapMs=$doubleSnapMinGapMs, cooldownMs=$cooldownMs');

    // Route audio to glasses mic.
    try {
      debugPrint('[SnapDetector] Routing audio to glasses mic...');
      final r = await _channel.invokeMethod('routeAudioToGlassesMic');
      if (r is Map) {
        debugPrint('[SnapDetector] Audio routed: '
            '${r['routed'] == true ? "✓ Glasses HFP" : "✗ Phone mic"} '
            '(${r['inputName']}, ${r['inputType']})');
      }
    } catch (e) {
      debugPrint('[SnapDetector] Audio route failed: $e');
    }

    _voiceProcessor = VoiceProcessor.instance;
    _frameListener = (List<int> frame) => _processFrame(frame);
    _voiceProcessor!.addFrameListener(_frameListener);

    try {
      await _voiceProcessor!.start(_frameLength, _sampleRate);
      _running = true;
      _resetStats();
      _resetFilterState();
      debugPrint('[SnapDetector] ✓ Listening (ZCR + bandpass approach).');
    } catch (e) {
      debugPrint('[SnapDetector] ✗ Start failed: $e');
      _voiceProcessor!.removeFrameListener(_frameListener);
      rethrow;
    }
  }

  Future<void> stop() async {
    if (!_running) return;
    _running = false;
    _uptimeWatch.stop();

    try {
      await _voiceProcessor?.stop();
    } catch (_) {}
    _voiceProcessor?.removeFrameListener(_frameListener);
    _awaitingSecondSnap = false;

    debugPrint('[SnapDetector] ── STOPPED ───────────────────────────────');
    debugPrint('[SnapDetector] Uptime: ${_uptimeWatch.elapsed.inSeconds}s, '
        'frames: $_totalFrames');
    debugPrint('[SnapDetector] Ambient: ${_ambientRms.toStringAsFixed(0)}, '
        'peakRms: ${_peakRms.toStringAsFixed(0)}, '
        'peakZcr: ${_peakZcr.toStringAsFixed(3)}, '
        'peakSpike: ${_peakSpikeRatio.toStringAsFixed(1)}x');
    debugPrint('[SnapDetector] passedSpike=$_framesPassedSpike, '
        'passedZcr=$_framesPassedZcr, '
        'sustained=$_framesSustainedRejected, '
        'cooldown=$_framesCooldownRejected, '
        'echo=$_framesEchoRejected, '
        'windowExpired=$_framesWindowExpired');
    debugPrint('[SnapDetector] Snaps triggered: $_snapsDetected');
  }

  void dispose() {
    stop();
  }

  // ── Recording ────────────────────────────────────────────────────────

  void startRecording() {
    _recordBuffer.clear();
    _recording = true;
    debugPrint('[SnapDetector] ● REC started');
  }

  Future<String?> stopRecording() async {
    if (!_recording) return null;
    _recording = false;
    if (_recordBuffer.isEmpty) return null;

    final dur = _recordBuffer.length / _sampleRate;
    debugPrint('[SnapDetector] ● REC stopped: ${dur.toStringAsFixed(1)}s');

    try {
      final dir = await getApplicationDocumentsDirectory();
      final ts = DateTime.now().toIso8601String().replaceAll(':', '-');
      final path = '${dir.path}/snap_debug_$ts.wav';
      await File(path).writeAsBytes(_encodeWav(_recordBuffer, _sampleRate));
      _lastRecordingPath = path;
      _recordBuffer.clear();
      debugPrint('[SnapDetector] ✓ WAV saved: $path');
      return path;
    } catch (e) {
      debugPrint('[SnapDetector] ✗ WAV save failed: $e');
      _recordBuffer.clear();
      return null;
    }
  }

  /// Play a WAV file through the native AVAudioPlayer (no extra plugin).
  Future<void> playRecording(String path) async {
    try {
      await _channel.invokeMethod('playAudioFile', {'path': path});
      debugPrint('[SnapDetector] Playing: $path');
    } catch (e) {
      debugPrint('[SnapDetector] Playback error: $e');
    }
  }

  Future<void> stopPlayback() async {
    try {
      await _channel.invokeMethod('stopAudioPlayback');
    } catch (_) {}
  }

  // ── Detection logic ──────────────────────────────────────────────────

  void _processFrame(List<int> frame) {
    _totalFrames++;

    // Record raw PCM if active.
    if (_recording && _recordBuffer.length < _maxRecordSamples) {
      _recordBuffer.addAll(frame);
    } else if (_recording && _recordBuffer.length >= _maxRecordSamples) {
      _recording = false;
      debugPrint('[SnapDetector] ● REC auto-stopped (60s limit)');
    }

    // 1. Apply bandpass filter (1–3.5 kHz).
    final filtered = _applyBandpass(frame);

    // 2. Compute features on filtered signal.
    final fRms = _computeRms(filtered);
    final zcr = _computeZcr(filtered);

    if (fRms > _peakRms) _peakRms = fRms;
    if (zcr > _peakZcr) _peakZcr = zcr;

    // First frame log.
    if (_totalFrames == 1) {
      debugPrint('[SnapDetector] ✓ First frame: '
          'filteredRms=${fRms.toStringAsFixed(0)}, zcr=${zcr.toStringAsFixed(3)}');
    }

    // Update ambient (only with quiet frames).
    if (!_ambientInitialized) {
      _ambientRms = fRms;
      _ambientInitialized = true;
    } else if (fRms < _ambientRms * 3.0 || fRms < minFilteredRms) {
      _ambientRms = _ambientRms * (1.0 - _ambientAlpha) + fRms * _ambientAlpha;
    }

    final spikeRatio = _ambientRms > 0.5 ? fRms / _ambientRms : 0.0;
    if (spikeRatio > _peakSpikeRatio) _peakSpikeRatio = spikeRatio;

    // Periodic stats.
    if (_totalFrames % _logEveryNFrames == 0) {
      debugPrint('[SnapDetector] [${_uptimeWatch.elapsed.inSeconds}s] '
          'frames=$_totalFrames, '
          'fRms=${fRms.toStringAsFixed(0)}, '
          'amb=${_ambientRms.toStringAsFixed(0)}, '
          'spike=${spikeRatio.toStringAsFixed(1)}x, '
          'zcr=${zcr.toStringAsFixed(3)}, '
          'hot=$_consecutiveHotFrames, '
          'snaps=$_snapsDetected');
    }

    // ── Gate 1: Spike (filtered RMS above ambient) ──────────────────
    final isHot = fRms >= minFilteredRms && spikeRatio >= spikeMultiplier;

    if (!isHot) {
      if (_consecutiveHotFrames > 0) {
        debugPrint('[SnapDetector] Hot streak ended: $_consecutiveHotFrames frames');
      }
      _consecutiveHotFrames = 0;
      return;
    }

    _consecutiveHotFrames++;
    _framesPassedSpike++;

    debugPrint('[SnapDetector] ✓ Spike: '
        'fRms=${fRms.toStringAsFixed(0)}, '
        'amb=${_ambientRms.toStringAsFixed(0)}, '
        'ratio=${spikeRatio.toStringAsFixed(1)}x, '
        'zcr=${zcr.toStringAsFixed(3)}, '
        'hot=$_consecutiveHotFrames');

    // ── Gate 2: Sustained sound rejection ───────────────────────────
    if (_consecutiveHotFrames > maxHotFrames) {
      _framesSustainedRejected++;
      if (_consecutiveHotFrames == maxHotFrames + 1) {
        debugPrint('[SnapDetector] ✗ SUSTAINED SOUND '
            '($_consecutiveHotFrames frames > $maxHotFrames). Speech/music.');
      }
      if (_awaitingSecondSnap) {
        _awaitingSecondSnap = false;
        debugPrint('[SnapDetector]   Cancelled pending first-snap.');
      }
      return;
    }

    // ── Gate 3: Zero Crossing Rate ──────────────────────────────────
    if (zcr < minZcr) {
      debugPrint('[SnapDetector] ✗ ZCR too low: '
          '${zcr.toStringAsFixed(3)} < $minZcr. '
          'Periodic sound (speech), not broadband snap.');
      return;
    }

    _framesPassedZcr++;
    final now = DateTime.now();

    debugPrint('[SnapDetector] ☆ CANDIDATE #$_framesPassedZcr '
        '(fRms=${fRms.toStringAsFixed(0)}, spike=${spikeRatio.toStringAsFixed(1)}x, '
        'zcr=${zcr.toStringAsFixed(3)}, hot=$_consecutiveHotFrames)');

    // ── Gate 4: Cooldown ────────────────────────────────────────────
    final msSince = now.difference(_lastTriggerTime).inMilliseconds;
    if (msSince < cooldownMs) {
      _framesCooldownRejected++;
      return;
    }

    // ── Gate 5: Double-snap ─────────────────────────────────────────
    if (requireDoubleSnap) {
      if (!_awaitingSecondSnap) {
        _firstSnapTime = now;
        _awaitingSecondSnap = true;
        debugPrint('[SnapDetector] → First snap. '
            'Waiting ${doubleSnapMinGapMs}–${doubleSnapWindowMs}ms...');
        return;
      }

      final gap = now.difference(_firstSnapTime).inMilliseconds;
      if (gap < doubleSnapMinGapMs) {
        _framesEchoRejected++;
        debugPrint('[SnapDetector] → Echo (${gap}ms)');
        return;
      }
      if (gap > doubleSnapWindowMs) {
        _framesWindowExpired++;
        _firstSnapTime = now;
        debugPrint('[SnapDetector] → Window expired (${gap}ms). New first snap.');
        return;
      }

      _awaitingSecondSnap = false;
      debugPrint('[SnapDetector] → Second snap at ${gap}ms!');
    }

    // ── TRIGGER ─────────────────────────────────────────────────────
    _lastTriggerTime = now;
    _snapsDetected++;
    debugPrint('[SnapDetector] ★★★ SNAP #$_snapsDetected ★★★ '
        '(fRms=${fRms.toStringAsFixed(0)}, zcr=${zcr.toStringAsFixed(3)}, '
        'spike=${spikeRatio.toStringAsFixed(1)}x)');
    _onSnap?.call();
  }

  // ── DSP helpers ──────────────────────────────────────────────────────

  /// Apply 2nd-order Butterworth bandpass (1–3.5 kHz at 16 kHz).
  /// Maintains filter state across frames for continuity.
  List<double> _applyBandpass(List<int> frame) {
    final out = List<double>.filled(frame.length, 0);
    for (var i = 0; i < frame.length; i++) {
      final x = frame[i].toDouble();

      final y = _bpB[0] * x +
          _bpB[1] * _bpX[0] +
          _bpB[2] * _bpX[1] +
          _bpB[3] * _bpX[2] +
          _bpB[4] * _bpX[3] -
          _bpA[1] * _bpY[0] -
          _bpA[2] * _bpY[1] -
          _bpA[3] * _bpY[2] -
          _bpA[4] * _bpY[3];

      // Shift delay lines.
      _bpX[3] = _bpX[2];
      _bpX[2] = _bpX[1];
      _bpX[1] = _bpX[0];
      _bpX[0] = x;
      _bpY[3] = _bpY[2];
      _bpY[2] = _bpY[1];
      _bpY[1] = _bpY[0];
      _bpY[0] = y;

      out[i] = y;
    }
    return out;
  }

  double _computeRms(List<double> frame) {
    double sum = 0;
    for (final s in frame) {
      sum += s * s;
    }
    return sqrt(sum / frame.length);
  }

  /// Zero Crossing Rate: fraction of adjacent samples that cross zero.
  /// Range: 0.0 (DC / pure tone) to ~0.5 (white noise).
  /// Snaps (broadband): > 0.3. Speech (periodic): 0.05–0.20.
  double _computeZcr(List<double> frame) {
    if (frame.length < 2) return 0;
    int crossings = 0;
    for (var i = 1; i < frame.length; i++) {
      if ((frame[i] >= 0 && frame[i - 1] < 0) ||
          (frame[i] < 0 && frame[i - 1] >= 0)) {
        crossings++;
      }
    }
    return crossings / (frame.length - 1);
  }

  void _resetStats() {
    _totalFrames = 0;
    _snapsDetected = 0;
    _peakRms = 0;
    _peakZcr = 0;
    _peakSpikeRatio = 0;
    _framesPassedSpike = 0;
    _framesPassedZcr = 0;
    _framesSustainedRejected = 0;
    _framesCooldownRejected = 0;
    _framesEchoRejected = 0;
    _framesWindowExpired = 0;
    _consecutiveHotFrames = 0;
    _ambientRms = 0;
    _ambientInitialized = false;
    _awaitingSecondSnap = false;
    _uptimeWatch.reset();
    _uptimeWatch.start();
  }

  void _resetFilterState() {
    for (var i = 0; i < 4; i++) {
      _bpX[i] = 0;
      _bpY[i] = 0;
    }
  }

  Uint8List _encodeWav(List<int> samples, int sampleRate) {
    final n = samples.length;
    const bps = 16;
    const ch = 1;
    final byteRate = sampleRate * ch * bps ~/ 8;
    const blockAlign = ch * bps ~/ 8;
    final dataSize = n * blockAlign;
    final buf = ByteData(44 + dataSize);
    var o = 0;

    void s(String v) {
      for (var i = 0; i < v.length; i++) {
        buf.setUint8(o++, v.codeUnitAt(i));
      }
    }

    void u32(int v) {
      buf.setUint32(o, v, Endian.little);
      o += 4;
    }

    void u16(int v) {
      buf.setUint16(o, v, Endian.little);
      o += 2;
    }

    s('RIFF');
    u32(36 + dataSize);
    s('WAVE');
    s('fmt ');
    u32(16);
    u16(1);
    u16(ch);
    u32(sampleRate);
    u32(byteRate);
    u16(blockAlign);
    u16(bps);
    s('data');
    u32(dataSize);

    for (final sample in samples) {
      buf.setInt16(o, sample.clamp(-32768, 32767), Endian.little);
      o += 2;
    }
    return buf.buffer.asUint8List();
  }
}
