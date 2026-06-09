import "../core/api_client.dart";
import "borrower_models.dart";

typedef BorrowerJsonFetcher = Future<Map<String, dynamic>> Function(String path);

class BorrowerApiService {
  BorrowerApiService({ApiClient? apiClient, BorrowerJsonFetcher? getJson})
      : assert(apiClient != null || getJson != null),
        _getJson = getJson ?? apiClient!.getJson;

  final BorrowerJsonFetcher _getJson;

  Future<BorrowerSearchResult> searchBorrowers({String? fullName}) async {
    final String query = fullName == null || fullName.isEmpty
        ? ""
        : "?fullName=${Uri.encodeQueryComponent(fullName)}";
    final Map<String, dynamic> payload = await _getJson("/borrowers$query");
    return BorrowerSearchResult.fromJson(payload);
  }

  Future<BorrowerSummary> getBorrowerById(String borrowerId) async {
    final Map<String, dynamic> payload = await _getJson("/borrowers/$borrowerId");
    return BorrowerSummary.fromJson(payload);
  }
}
