import "dart:convert";

import "package:http/http.dart" as http;

import "app_config.dart";
import "../auth/auth_service.dart";

class ApiClient {
  ApiClient({
    required AppConfig config,
    required AuthService authService,
    http.Client? httpClient,
  })  : _config = config,
        _authService = authService,
        _httpClient = httpClient ?? http.Client();

  final AppConfig _config;
  final AuthService _authService;
  final http.Client _httpClient;

  Future<Map<String, dynamic>> getJson(String path) async {
    final bool signedIn = await _authService.isSignedIn();
    final Map<String, String> headers = {
      "Content-Type": "application/json",
      if (signedIn) "Authorization": "Bearer ${AuthService.placeholderToken}",
    };

    final Uri uri = Uri.parse("${_config.apiBaseUrl}$path");
    final http.Response response = await _httpClient.get(uri, headers: headers);

    if (response.statusCode < 200 || response.statusCode > 299) {
      throw Exception("API request failed: ${response.statusCode}");
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
