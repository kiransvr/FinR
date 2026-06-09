import "package:flutter/material.dart";

import "borrower_api_service.dart";
import "borrower_models.dart";

class BorrowerListScreen extends StatefulWidget {
  const BorrowerListScreen({
    required this.apiService,
    this.onOpenBorrowerDetail,
    this.onOpenCreateEditPlaceholder,
    super.key,
  });

  final BorrowerApiService apiService;
  final void Function(String borrowerId)? onOpenBorrowerDetail;
  final VoidCallback? onOpenCreateEditPlaceholder;

  @override
  State<BorrowerListScreen> createState() => _BorrowerListScreenState();
}

class _BorrowerListScreenState extends State<BorrowerListScreen> {
  final TextEditingController _controller = TextEditingController();
  List<BorrowerSummary> _items = <BorrowerSummary>[];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final BorrowerSearchResult result = await widget.apiService.searchBorrowers(fullName: _controller.text);
      if (!mounted) {
        return;
      }
      setState(() {
        _items = result.items;
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
      appBar: AppBar(title: const Text("Borrowers")),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(labelText: "Search by name"),
                  ),
                ),
                const SizedBox(width: 12),
                FilledButton(onPressed: _search, child: const Text("Search")),
              ],
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: widget.onOpenCreateEditPlaceholder,
              child: const Text("Open Create/Edit Placeholder"),
            ),
            const SizedBox(height: 16),
            if (_loading) const CircularProgressIndicator(),
            if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
            if (!_loading)
              Expanded(
                child: ListView.builder(
                  itemCount: _items.length,
                  itemBuilder: (BuildContext context, int index) {
                    final BorrowerSummary borrower = _items[index];
                    return ListTile(
                      title: Text(borrower.fullName),
                      subtitle: Text("${borrower.phoneNumber} • ${borrower.status}"),
                      onTap: () => widget.onOpenBorrowerDetail?.call(borrower.id),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
