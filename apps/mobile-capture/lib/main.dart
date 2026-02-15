import 'package:flutter/material.dart';

import 'screens/capture_screen.dart';
import 'screens/stream_screen.dart';
import 'widgets/glass_container.dart';

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
        scaffoldBackgroundColor: const Color(0xFF060B0D),
        fontFamily: '.SF Pro Text',
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
      backgroundColor: Colors.transparent,
      body: AestheticaBackground(
        child: Stack(
          children: [
            // Decorative glow orbs.
            const GlowOrb(
              color: Color(0xFF1A6B5C),
              size: 320,
              alignment: Alignment(-1.2, -0.8),
              opacity: 0.10,
            ),
            const GlowOrb(
              color: Color(0xFF1A3D6B),
              size: 250,
              alignment: Alignment(1.0, -0.3),
              opacity: 0.08,
            ),
            const GlowOrb(
              color: Color(0xFF6B4A1A),
              size: 200,
              alignment: Alignment(0.2, 1.2),
              opacity: 0.06,
            ),

            // Content.
            SafeArea(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 32),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // Logo area.
                      const Text(
                        'AESTHETICA',
                        style: TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.w200,
                          color: Color(0xFFF0EDE5),
                          letterSpacing: 6.0,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Fashion capture for Meta Ray-Ban',
                        style: TextStyle(
                          color: const Color(0xFFAFA79A).withOpacity(0.7),
                          fontSize: 13,
                          fontWeight: FontWeight.w300,
                          letterSpacing: 0.5,
                        ),
                      ),
                      const SizedBox(height: 56),

                      // Mode cards.
                      _GlassModeCard(
                        icon: Icons.camera_alt_outlined,
                        title: 'Capture',
                        subtitle: 'Single-shot capture via snap gesture',
                        accentColor: const Color(0xFFF5B342),
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                              builder: (_) => const CaptureScreen()),
                        ),
                      ),
                      const SizedBox(height: 16),
                      _GlassModeCard(
                        icon: Icons.stream,
                        title: 'Live Stream',
                        subtitle: 'Real-time video stream with live analysis',
                        accentColor: const Color(0xFF3CE37D),
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
          ],
        ),
      ),
    );
  }
}

class _GlassModeCard extends StatelessWidget {
  const _GlassModeCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    required this.accentColor,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color accentColor;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: GlassContainer(
        padding: const EdgeInsets.all(20),
        borderRadius: 22,
        child: Row(
          children: [
            // Icon with glow.
            Container(
              width: 50,
              height: 50,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                color: accentColor.withOpacity(0.12),
                border: Border.all(
                  color: accentColor.withOpacity(0.2),
                  width: 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: accentColor.withOpacity(0.15),
                    blurRadius: 16,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: Icon(icon, color: accentColor, size: 22),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Color(0xFFF0EDE5),
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.3,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: const Color(0xFFAFA79A).withOpacity(0.7),
                      fontSize: 12,
                      fontWeight: FontWeight.w300,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              color: Colors.white.withOpacity(0.3),
            ),
          ],
        ),
      ),
    );
  }
}
