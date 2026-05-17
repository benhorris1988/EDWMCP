import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../widgets/section.dart';

class EdwScreen extends StatefulWidget {
  const EdwScreen({super.key});

  @override
  State<EdwScreen> createState() => _EdwScreenState();
}

class _EdwScreenState extends State<EdwScreen> {
  Map<String, dynamic>? _skills;
  String? _error;
  bool _saving = false;
  late final TextEditingController _maxRows;
  late final TextEditingController _allowedSchemas;
  bool _enabled = true;

  @override
  void initState() {
    super.initState();
    _maxRows = TextEditingController();
    _allowedSchemas = TextEditingController();
    _load();
  }

  Future<void> _load() async {
    try {
      final s = await context.read<AppState>().client!.getSkills();
      final edw = (s['edw'] as Map).cast<String, dynamic>();
      setState(() {
        _skills = s;
        _enabled = edw['enabled'] != false;
        _maxRows.text = edw['max_rows'].toString();
        _allowedSchemas.text = (edw['allowed_schemas'] as List).join(', ');
        _error = null;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final s = Map<String, dynamic>.from(_skills!);
      final edw = Map<String, dynamic>.from(s['edw'] as Map);
      edw['enabled'] = _enabled;
      edw['max_rows'] = int.tryParse(_maxRows.text) ?? edw['max_rows'];
      edw['allowed_schemas'] =
          _allowedSchemas.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
      s['edw'] = edw;
      await context.read<AppState>().client!.updateSkills(s);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Saved. Restart edwmcp for changes to take effect.')),
        );
      }
      await _load();
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_skills == null && _error == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(_error!, style: const TextStyle(color: Colors.redAccent)),
          ),
        Section(
          title: 'EDW skill',
          subtitle: 'Generic warehouse introspection + guarded SELECT-only run_query.',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SwitchListTile(
                title: const Text('Skill enabled'),
                value: _enabled,
                onChanged: (v) => setState(() => _enabled = v),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _maxRows,
                decoration: const InputDecoration(
                  labelText: 'Max rows per query',
                  helperText: 'Hard-enforced in addition to the server-wide EDWMCP_QUERY_MAX_ROWS.',
                ),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _allowedSchemas,
                decoration: const InputDecoration(
                  labelText: 'Allowed schemas (comma-separated)',
                  helperText: 'Empty list = no restriction (subject to DB user permissions).',
                ),
              ),
            ],
          ),
        ),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(_saving ? 'Saving…' : 'Save'),
          ),
        ),
      ],
    );
  }
}
