/// Mirrors the backend `CatalogFromImageResponse` schema.
class CatalogResult {
  CatalogResult({
    required this.requestId,
    required this.pipelineStatus,
    required this.recommendations,
    this.garmentName,
    this.brandHint,
    this.confidence,
    this.error,
  });

  factory CatalogResult.fromJson(Map<String, dynamic> json) {
    final recs = (json['recommendations'] as List<dynamic>? ?? [])
        .map((e) =>
            CatalogRecommendation.fromJson(e as Map<String, dynamic>))
        .toList();
    return CatalogResult(
      requestId: json['request_id'] as String? ?? '',
      pipelineStatus: json['pipeline_status'] as String? ?? 'unknown',
      garmentName: json['garment_name'] as String?,
      brandHint: json['brand_hint'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      error: json['error'] as String?,
      recommendations: recs,
    );
  }

  final String requestId;
  final String pipelineStatus;
  final String? garmentName;
  final String? brandHint;
  final double? confidence;
  final String? error;
  final List<CatalogRecommendation> recommendations;

  bool get isOk => pipelineStatus == 'ok';
  bool get hasResults => recommendations.isNotEmpty;
}

class CatalogRecommendation {
  CatalogRecommendation({
    required this.rank,
    required this.title,
    required this.productUrl,
    this.source,
    this.priceText,
    this.priceValue,
    this.imageUrl,
  });

  factory CatalogRecommendation.fromJson(Map<String, dynamic> json) {
    return CatalogRecommendation(
      rank: json['rank'] as int? ?? 0,
      title: json['title'] as String? ?? '',
      productUrl: json['product_url'] as String? ?? '',
      source: json['source'] as String?,
      priceText: json['price_text'] as String?,
      priceValue: (json['price_value'] as num?)?.toDouble(),
      imageUrl: json['recommendation_image_url'] as String?,
    );
  }

  final int rank;
  final String title;
  final String productUrl;
  final String? source;
  final String? priceText;
  final double? priceValue;
  final String? imageUrl;
}
