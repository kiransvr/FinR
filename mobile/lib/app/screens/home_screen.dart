import "package:flutter/material.dart";

import "../auth/auth_service.dart";
import "../navigation/app_router.dart";

class HomeScreen extends StatefulWidget {
  const HomeScreen({required this.authService, super.key});

  final AuthService authService;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _authenticated = false;

  @override
  void initState() {
    super.initState();
    _loadAuthState();
  }

  Future<void> _loadAuthState() async {
    final bool signedIn = await widget.authService.isSignedIn();
    if (!mounted) {
      return;
    }
    setState(() {
      _authenticated = signedIn;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("FinG Mobile Shell")),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Sprint 1 placeholder for collections and recovery workflows.",
            ),
            const SizedBox(height: 16),
            Text(_authenticated ? "Session: Placeholder active" : "Session: Not signed in"),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => Navigator.of(context).pushNamed(AppRouter.signInRoute),
              child: const Text("Go to Sign In"),
            ),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: () => Navigator.of(context).pushNamed(AppRouter.borrowersRoute),
              child: const Text("Open Borrowers"),
            ),
          ],
        ),
      ),
    );
  }
}
