import "token_store.dart";

class AuthService {
  AuthService({TokenStore? tokenStore}) : _tokenStore = tokenStore ?? InMemoryTokenStore();

  static const String placeholderToken = "fing-mobile-placeholder-token";

  final TokenStore _tokenStore;

  Future<bool> isSignedIn() async {
    final String? token = await _tokenStore.readToken();
    return token != null && token.isNotEmpty;
  }

  Future<void> signInWithPlaceholderToken() async {
    await _tokenStore.writeToken(placeholderToken);
  }

  Future<void> signOut() async {
    await _tokenStore.clearToken();
  }
}
