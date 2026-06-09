import "package:flutter/material.dart";

import "borrower_api_service.dart";
import "borrower_models.dart";

class BorrowerDetailScreen extends StatefulWidget {
  const BorrowerDetailScreen({
    required this.borrowerId,
    required this.apiService,
    this.onOpenCreateEditPlaceholder,
    super.key,
  });

  final String borrowerId;
  final BorrowerApiService apiService;
  final VoidCallback? onOpenCreateEditPlaceholder;

  @override
  State<BorrowerDetailScreen> createState() => _BorrowerDetailScreenState();
}

class _BorrowerDetailScreenState extends State<BorrowerDetailScreen> {
  BorrowerSummary? _borrower;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadBorrower();
  }

  Future<void> _loadBorrower() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final BorrowerSummary borrower = await widget.apiService.getBorrowerById(widget.borrowerId);
      if (!mounted) {
        return;
      }
      setState(() {
        _borrower = borrower;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.toString();
      });
    } finally {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Borrower Detail")),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            if (_loading) const CircularProgressIndicator(),
            if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
            if (!_loading && _borrower != null) ...<Widget>[
              Text(_borrower!.fullName, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text("Phone: ${_borrower!.phoneNumber}"),
              const SizedBox(height: 4),
              Text("Status: ${_borrower!.status}"),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: widget.onOpenCreateEditPlaceholder,
                child: const Text("Open Create/Edit Placeholder"),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
