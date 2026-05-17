import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../widgets/section.dart';

class ToolsScreen extends StatefulWidget {
  const ToolsScreen({super.key});

  @override
  State<ToolsScreen> createState() => _ToolsScreenState();
}

class _ToolsScreenState extends State<ToolsScreen> {
  List<dynamic>? _tools;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final t = await context.read<AppState>().client!.listTools();
      setState(() {
        _tools = t;
        _error = null;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_tools == null && _error == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(child: Text(_error!, style: const TextStyle(color: Colors.redAccent)));
    }
    final tools = _tools!;
    final byPrefix = <String, List<Map<String, dynamic>>>{};
    for (final t in tools) {
      final m = (t as Map).cast<String, dynamic>();
      final prefix = m['name'].toString().split('_').first;
      byPrefix.putIfAbsent(prefix, () => []).add(m);
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        for (final entry in byPrefix.entries)
          Section(
            title: '${entry.key} skill (${entry.value.length} tools)',
            child: Column(
              children: [
                for (final t in entry.value) _ToolRow(t),
              ],
            ),
          ),
      ],
    );
  }
}

class _ToolRow extends StatelessWidget {
  const _ToolRow(this.tool);

  final Map<String, dynamic> tool;

  @override
  Widget build(BuildContext context) {
    final ann = (tool['annotations'] as Map?)?.cast<String, dynamic>() ?? {};
    final readOnly = ann['readOnlyHint'] == true;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(tool['name'].toString(),
                  style: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.w600)),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: readOnly ? Colors.green.withOpacity(0.2) : Colors.orange.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  readOnly ? 'read-only' : 'mutating',
                  style: TextStyle(color: readOnly ? Colors.greenAccent : Colors.orangeAccent, fontSize: 11),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            tool['description'].toString().split('\n').first,
            style: TextStyle(color: Colors.grey.shade400, fontSize: 13),
          ),
        ],
      ),
    );
  }
}
