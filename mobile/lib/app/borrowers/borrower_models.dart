class BorrowerSummary {
  BorrowerSummary({
    required this.id,
    required this.fullName,
    required this.phoneNumber,
    required this.status,
  });

  final String id;
  final String fullName;
  final String phoneNumber;
  final String status;

  factory BorrowerSummary.fromJson(Map<String, dynamic> json) {
    return BorrowerSummary(
      id: json["id"] as String,
      fullName: json["fullName"] as String,
      phoneNumber: json["phoneNumber"] as String,
      status: json["status"] as String,
    );
  }
}

class BorrowerSearchResult {
  BorrowerSearchResult({required this.items});

  final List<BorrowerSummary> items;

  factory BorrowerSearchResult.fromJson(Map<String, dynamic> json) {
    final List<dynamic> rawItems = (json["items"] as List<dynamic>? ?? <dynamic>[]);
    return BorrowerSearchResult(
      items: rawItems.map((item) => BorrowerSummary.fromJson(item as Map<String, dynamic>)).toList(),
    );
  }
}
