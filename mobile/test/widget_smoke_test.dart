import "package:fing_mobile/app/app.dart";
import "package:flutter_test/flutter_test.dart";

void main() {
  testWidgets("app shell renders", (tester) async {
    await tester.pumpWidget(const FinGApp());

    expect(find.text("FinG Mobile Shell"), findsOneWidget);
    expect(find.text("Go to Sign In"), findsOneWidget);
  });
}
