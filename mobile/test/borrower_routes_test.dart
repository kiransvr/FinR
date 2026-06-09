import "package:fing_mobile/app/auth/auth_service.dart";
import "package:fing_mobile/app/borrowers/borrower_api_service.dart";
import "package:fing_mobile/app/navigation/app_router.dart";
import "package:flutter/material.dart";
import "package:flutter_test/flutter_test.dart";

void main() {
  BorrowerApiService buildFakeBorrowerService() {
    return BorrowerApiService(
      getJson: (String path) async {
        if (path.startsWith("/borrowers?")) {
          return <String, dynamic>{
            "items": <Map<String, dynamic>>[
              <String, dynamic>{
                "id": "b-1",
                "fullName": "Asha Kumar",
                "phoneNumber": "9876543210",
                "status": "ACTIVE",
              }
            ]
          };
        }
        if (path == "/borrowers/b-1") {
          return <String, dynamic>{
            "id": "b-1",
            "fullName": "Asha Kumar",
            "phoneNumber": "9876543210",
            "status": "ACTIVE",
          };
        }
        return <String, dynamic>{"items": <Map<String, dynamic>>[]};
      },
    );
  }

  testWidgets("borrower list route renders and navigates to detail", (tester) async {
    final AuthService authService = AuthService();

    await tester.pumpWidget(
      MaterialApp(
        initialRoute: AppRouter.borrowersRoute,
        onGenerateRoute: (RouteSettings settings) => AppRouter.onGenerateRoute(
          settings,
          authService,
          borrowerApiServiceBuilder: (_) => buildFakeBorrowerService(),
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text("Borrowers"), findsOneWidget);
    expect(find.text("Asha Kumar"), findsOneWidget);

    await tester.tap(find.text("Asha Kumar"));
    await tester.pumpAndSettle();

    expect(find.text("Borrower Detail"), findsOneWidget);
    expect(find.text("Phone: 9876543210"), findsOneWidget);
  });

  testWidgets("create/edit placeholder route is reachable", (tester) async {
    final AuthService authService = AuthService();

    await tester.pumpWidget(
      MaterialApp(
        initialRoute: AppRouter.borrowersRoute,
        onGenerateRoute: (RouteSettings settings) => AppRouter.onGenerateRoute(
          settings,
          authService,
          borrowerApiServiceBuilder: (_) => buildFakeBorrowerService(),
        ),
      ),
    );

    await tester.pumpAndSettle();

    await tester.tap(find.text("Open Create/Edit Placeholder"));
    await tester.pumpAndSettle();

    expect(find.text("Create/Edit Borrower Placeholder"), findsOneWidget);
  });
}
