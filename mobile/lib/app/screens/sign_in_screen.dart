import "package:flutter/material.dart";

import "../auth/auth_service.dart";

class SignInScreen extends StatefulWidget {
  const SignInScreen({required this.authService, super.key});

  final AuthService authService;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  bool _loading = false;

  Future<void> _signIn() async {
    setState(() {
      _loading = true;
    });
    await widget.authService.signInWithPlaceholderToken();
    if (!mounted) {
      return;
    }
    setState(() {
      _loading = false;
    });
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Sign In Placeholder")),
      body: Center(
        child: FilledButton(
          onPressed: _loading ? null : _signIn,
          child: Text(_loading ? "Signing in..." : "Sign In"),
        ),
      ),
    );
  }
}
