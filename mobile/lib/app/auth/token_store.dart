abstract class TokenStore {
  Future<String?> readToken();
  Future<void> writeToken(String token);
  Future<void> clearToken();
}

class InMemoryTokenStore implements TokenStore {
  String? _token;

  @override
  Future<void> clearToken() async {
    _token = null;
  }

  @override
  Future<String?> readToken() async {
    return _token;
  }

  @override
  Future<void> writeToken(String token) async {
    _token = token;
  }
}
