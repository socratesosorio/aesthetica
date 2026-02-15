import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models/catalog_result.dart';

class CaptureApiClient {
  CaptureApiClient({
    required this.baseUrl,
    required this.authToken,
  });

  final String baseUrl;
  final String authToken;

  /// Original capture upload — sends image to the ML pipeline.
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

  /// Sends an image to the catalog-from-image endpoint which uses
  /// OpenAI Vision + Google Shopping to find matching products.
  Future<CatalogResult> catalogFromImage(Uint8List jpegBytes) async {
    final uri = Uri.parse('$baseUrl/v1/catalog/from-image');

    // Send as raw body with image/jpeg content-type.
    // The endpoint accepts both multipart form and raw body.
    final response = await http.post(
      uri,
      headers: {
        'Authorization': 'Bearer $authToken',
        'Content-Type': 'image/jpeg',
      },
      body: jpegBytes,
    );

    if (response.statusCode >= 300) {
      throw Exception(
          'Catalog request failed: ${response.statusCode} ${response.body}');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return CatalogResult.fromJson(data);
  }
}
