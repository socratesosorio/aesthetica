import 'package:flutter/material.dart';

/// A translucent reticle overlay with L-shaped corner brackets and subtle
/// crosshair lines — lighter and more elegant than a full border.
class ReticleOverlay extends StatelessWidget {
  const ReticleOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final w = constraints.maxWidth * 0.55;
          final h = constraints.maxHeight * 0.70;
          final left = (constraints.maxWidth - w) / 2;
          final top = (constraints.maxHeight - h) / 2;

          const bracketLen = 28.0;
          const thickness = 2.0;
          const color = Color(0x66FFFFFF); // translucent white
          const crosshairColor = Color(0x22FFFFFF);
          const radius = 4.0;

          return Stack(
            children: [
              // ── Crosshair lines ──────────────────────────────
              // Horizontal.
              Positioned(
                top: constraints.maxHeight / 2 - 0.5,
                left: left + bracketLen + 4,
                right: constraints.maxWidth - left - w + bracketLen + 4,
                child: Container(height: 1, color: crosshairColor),
              ),
              // Vertical.
              Positioned(
                left: constraints.maxWidth / 2 - 0.5,
                top: top + bracketLen + 4,
                bottom: constraints.maxHeight - top - h + bracketLen + 4,
                child: Container(width: 1, color: crosshairColor),
              ),

              // ── Top-left bracket ─────────────────────────────
              // Horizontal arm.
              Positioned(
                top: top,
                left: left,
                child: Container(
                  width: bracketLen,
                  height: thickness,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),
              // Vertical arm.
              Positioned(
                top: top,
                left: left,
                child: Container(
                  width: thickness,
                  height: bracketLen,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),

              // ── Top-right bracket ────────────────────────────
              Positioned(
                top: top,
                right: constraints.maxWidth - left - w,
                child: Container(
                  width: bracketLen,
                  height: thickness,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),
              Positioned(
                top: top,
                right: constraints.maxWidth - left - w,
                child: Container(
                  width: thickness,
                  height: bracketLen,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),

              // ── Bottom-left bracket ──────────────────────────
              Positioned(
                bottom: constraints.maxHeight - top - h,
                left: left,
                child: Container(
                  width: bracketLen,
                  height: thickness,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),
              Positioned(
                bottom: constraints.maxHeight - top - h,
                left: left,
                child: Container(
                  width: thickness,
                  height: bracketLen,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),

              // ── Bottom-right bracket ─────────────────────────
              Positioned(
                bottom: constraints.maxHeight - top - h,
                right: constraints.maxWidth - left - w,
                child: Container(
                  width: bracketLen,
                  height: thickness,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),
              Positioned(
                bottom: constraints.maxHeight - top - h,
                right: constraints.maxWidth - left - w,
                child: Container(
                  width: thickness,
                  height: bracketLen,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(radius),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
