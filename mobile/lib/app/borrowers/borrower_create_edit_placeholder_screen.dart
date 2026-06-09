import "package:flutter/material.dart";

class BorrowerCreateEditPlaceholderScreen extends StatelessWidget {
  const BorrowerCreateEditPlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Create/Edit Borrower Placeholder")),
      body: const Padding(
        padding: EdgeInsets.all(16),
        child: Text(
          "This placeholder route confirms the create/edit path is wired for future full mobile borrower flows.",
        ),
      ),
    );
  }
}
