import 'package:flutter/material.dart';

class ReticleOverlay extends StatelessWidget {
  const ReticleOverlay({super.key});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final w = constraints.maxWidth * 0.55;
          final h = constraints.maxHeight * 0.70;

          return Stack(
            children: [
              Center(
                child: Container(
                  width: w,
                  height: h,
                  decoration: BoxDecoration(
                    border:
                        Border.all(color: const Color(0xFFF5B342), width: 3),
                    borderRadius: BorderRadius.circular(18),
                  ),
                ),
              ),
              Center(
                child: Container(
                  width: 12,
                  height: 12,
                  decoration: const BoxDecoration(
                    color: Color(0xFFF5B342),
                    shape: BoxShape.circle,
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
