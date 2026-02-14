import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

class CaptureApiClient {
  CaptureApiClient({
    required this.baseUrl,
    required this.authToken,
  });

  final String baseUrl;
  final String authToken;

  Future<String> uploadCapture(Uint8List jpegBytes) async {
    final uri = Uri.parse('$baseUrl/v1/captures');
    final req = http.MultipartRequest('POST', uri)
      ..headers['Authorization'] = 'Bearer $authToken'
      ..files.add(
        http.MultipartFile.fromBytes(
          'image',
          jpegBytes,
          filename: 'capture.jpg',
        ),
      );

    final streamed = await req.send();
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode >= 300) {
      throw Exception('Upload failed: ${response.statusCode} ${response.body}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return data['capture_id'] as String;
  }
}
