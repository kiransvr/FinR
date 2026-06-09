import "package:flutter/material.dart";

import "auth/auth_service.dart";
import "navigation/app_router.dart";

class FinGApp extends StatefulWidget {
  const FinGApp({super.key});

  @override
  State<FinGApp> createState() => _FinGAppState();
}

class _FinGAppState extends State<FinGApp> {
  final AuthService _authService = AuthService();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "FinG Mobile",
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0C6B58)),
        useMaterial3: true,
      ),
      initialRoute: AppRouter.homeRoute,
      onGenerateRoute: (settings) => AppRouter.onGenerateRoute(settings, _authService),
    );
  }
}
