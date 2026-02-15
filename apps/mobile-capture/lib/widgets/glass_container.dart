import 'dart:ui';

import 'package:flutter/material.dart';

/// A frosted-glass container with backdrop blur, translucent fill, and a
/// subtle luminous border. The core building block of the liquid glass UI.
class GlassContainer extends StatelessWidget {
  const GlassContainer({
    super.key,
    required this.child,
    this.borderRadius = 24,
    this.blur = 20,
    this.opacity = 0.06,
    this.borderOpacity = 0.12,
    this.padding,
    this.margin,
  });

  final Widget child;
  final double borderRadius;
  final double blur;
  final double opacity;
  final double borderOpacity;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(borderRadius),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(opacity),
              borderRadius: BorderRadius.circular(borderRadius),
              border: Border.all(
                color: Colors.white.withOpacity(borderOpacity),
                width: 1,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.15),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: child,
          ),
        ),
      ),
    );
  }
}

/// A circular glass-style icon button with optional label.
class GlassIconButton extends StatelessWidget {
  const GlassIconButton({
    super.key,
    required this.icon,
    required this.label,
    required this.onTap,
    this.iconColor,
    this.isActive = false,
    this.activeColor = const Color(0xFF3CE37D),
    this.size = 48,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color? iconColor;
  final bool isActive;
  final Color activeColor;
  final double size;

  @override
  Widget build(BuildContext context) {
    final color = iconColor ?? (isActive ? activeColor : Colors.white70);

    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ClipOval(
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
              child: Container(
                width: size,
                height: size,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isActive
                      ? activeColor.withOpacity(0.15)
                      : Colors.white.withOpacity(0.08),
                  border: Border.all(
                    color: isActive
                        ? activeColor.withOpacity(0.3)
                        : Colors.white.withOpacity(0.1),
                    width: 1,
                  ),
                ),
                child: Icon(icon, color: color, size: size * 0.46),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: TextStyle(
              color: color.withOpacity(0.85),
              fontSize: 10,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }
}

/// Common gradient background used across all screens.
class AestheticaBackground extends StatelessWidget {
  const AestheticaBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(-0.3, -0.5),
          radius: 1.6,
          colors: [
            Color(0xFF0F2027),
            Color(0xFF0B1519),
            Color(0xFF060B0D),
          ],
          stops: [0.0, 0.5, 1.0],
        ),
      ),
      child: child,
    );
  }
}

/// Decorative ambient glow orb for backgrounds.
class GlowOrb extends StatelessWidget {
  const GlowOrb({
    super.key,
    this.color = const Color(0xFF1A5C6B),
    this.size = 280,
    this.alignment = Alignment.topRight,
    this.opacity = 0.12,
  });

  final Color color;
  final double size;
  final Alignment alignment;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: IgnorePointer(
        child: Align(
          alignment: alignment,
          child: Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  color.withOpacity(opacity),
                  color.withOpacity(0),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
