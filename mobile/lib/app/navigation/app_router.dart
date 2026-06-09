import "package:flutter/material.dart";

import "../auth/auth_service.dart";
import "../borrowers/borrower_api_service.dart";
import "../borrowers/borrower_create_edit_placeholder_screen.dart";
import "../borrowers/borrower_detail_screen.dart";
import "../borrowers/borrower_list_screen.dart";
import "../core/api_client.dart";
import "../core/app_config.dart";
import "../screens/home_screen.dart";
import "../screens/sign_in_screen.dart";

typedef BorrowerApiServiceBuilder = BorrowerApiService Function(AuthService authService);

class AppRouter {
  static const String homeRoute = "/";
  static const String signInRoute = "/sign-in";
  static const String borrowersRoute = "/borrowers";
  static const String borrowerDetailRoute = "/borrowers/detail";
  static const String borrowerCreateEditPlaceholderRoute = "/borrowers/create-edit";

  static Route<dynamic> onGenerateRoute(
    RouteSettings settings,
    AuthService authService,
    {BorrowerApiServiceBuilder? borrowerApiServiceBuilder}
  ) {
    final BorrowerApiServiceBuilder serviceBuilder =
        borrowerApiServiceBuilder ?? _defaultBorrowerApiServiceBuilder;

    switch (settings.name) {
      case signInRoute:
        return MaterialPageRoute<void>(
          builder: (_) => SignInScreen(authService: authService),
          settings: settings,
        );
      case borrowersRoute:
        return MaterialPageRoute<void>(
          builder: (BuildContext context) => BorrowerListScreen(
            apiService: serviceBuilder(authService),
            onOpenBorrowerDetail: (String borrowerId) {
              Navigator.of(context).pushNamed(borrowerDetailRoute, arguments: borrowerId);
            },
            onOpenCreateEditPlaceholder: () {
              Navigator.of(context).pushNamed(borrowerCreateEditPlaceholderRoute);
            },
          ),
          settings: settings,
        );
      case borrowerDetailRoute:
        final Object? args = settings.arguments;
        if (args is! String || args.isEmpty) {
          return MaterialPageRoute<void>(
            builder: (_) => const Scaffold(
              body: Center(child: Text("Borrower detail route requires borrowerId.")),
            ),
            settings: settings,
          );
        }

        return MaterialPageRoute<void>(
          builder: (BuildContext context) => BorrowerDetailScreen(
            borrowerId: args,
            apiService: serviceBuilder(authService),
            onOpenCreateEditPlaceholder: () {
              Navigator.of(context).pushNamed(borrowerCreateEditPlaceholderRoute);
            },
          ),
          settings: settings,
        );
      case borrowerCreateEditPlaceholderRoute:
        return MaterialPageRoute<void>(
          builder: (_) => const BorrowerCreateEditPlaceholderScreen(),
          settings: settings,
        );
      case homeRoute:
      default:
        return MaterialPageRoute<void>(
          builder: (_) => HomeScreen(authService: authService),
          settings: settings,
        );
    }
  }

  static BorrowerApiService _defaultBorrowerApiServiceBuilder(AuthService authService) {
    final ApiClient apiClient = ApiClient(
      config: AppConfig(),
      authService: authService,
    );
    return BorrowerApiService(apiClient: apiClient);
  }
}
