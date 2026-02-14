import 'package:flutter/material.dart';

import 'screens/capture_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AestheticaCaptureApp());
}

class AestheticaCaptureApp extends StatelessWidget {
  const AestheticaCaptureApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Aesthetica Capture',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0D1414),
      ),
      home: const CaptureScreen(),
    );
  }
}
