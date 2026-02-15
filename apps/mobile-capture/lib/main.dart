import 'package:flutter/material.dart';

import 'screens/capture_screen.dart';
import 'screens/stream_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AestheticaCaptureApp());
}

class AestheticaCaptureApp extends StatelessWidget {
  const AestheticaCaptureApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Aesthetica',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0D1414),
      ),
      home: const _ModeSelector(),
    );
  }
}

/// Entry screen letting the user choose between single-capture and
/// live-stream mode.
class _ModeSelector extends StatelessWidget {
  const _ModeSelector();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1414),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Aesthetica',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFFFAF7EF),
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Fashion capture for Meta Ray-Ban',
                  style: TextStyle(color: Color(0xFFAFA79A), fontSize: 13),
                ),
                const SizedBox(height: 48),
                _ModeCard(
                  icon: Icons.camera_alt_outlined,
                  title: 'Capture',
                  subtitle: 'Single-shot capture via glasses button',
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const CaptureScreen()),
                  ),
                ),
                const SizedBox(height: 16),
                _ModeCard(
                  icon: Icons.stream,
                  title: 'Live Stream',
                  subtitle: 'Real-time video stream with live analysis',
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const StreamScreen()),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ModeCard extends StatelessWidget {
  const _ModeCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFF141E1E),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFF2A3838)),
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: const Color(0xFF1D2A2B),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: const Color(0xFFF5B342), size: 24),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Color(0xFFFAF7EF),
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: Color(0xFFAFA79A),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: Color(0xFFAFA79A)),
          ],
        ),
      ),
    );
  }
}
