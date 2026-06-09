class AppConfig {
  AppConfig({String? apiBaseUrl})
      : apiBaseUrl = apiBaseUrl ?? const String.fromEnvironment(
          "API_BASE_URL",
          defaultValue: "http://localhost:8080/api/v1",
        );

  final String apiBaseUrl;
}
