import "package:fing_mobile/app/auth/auth_service.dart";
import "package:flutter_test/flutter_test.dart";

void main() {
  test("auth service signs in with placeholder token", () async {
    final AuthService service = AuthService();

    expect(await service.isSignedIn(), isFalse);

    await service.signInWithPlaceholderToken();

    expect(await service.isSignedIn(), isTrue);
  });
}
