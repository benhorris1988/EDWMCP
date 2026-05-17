import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../widgets/section.dart';

class ConnectionsScreen extends StatefulWidget {
  const ConnectionsScreen({super.key});

  @override
  State<ConnectionsScreen> createState() => _ConnectionsScreenState();
}

class _ConnectionsScreenState extends State<ConnectionsScreen> {
  Map<String, dynamic>? _settings;
  late final TextEditingController _badminton;
  late final TextEditingController _edw;
  late final TextEditingController _maxRows;
  late final TextEditingController _timeout;
  String? _error;
  String? _badmintonTest;
  String? _edwTest;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _badminton = TextEditingController();
    _edw = TextEditingController();
    _maxRows = TextEditingController();
    _timeout = TextEditingController();
    _load();
  }

  Future<void> _load() async {
    try {
      final s = await context.read<AppState>().client!.getSettings();
      setState(() {
        _settings = s;
        _badminton.text = (s['badminton_url'] ?? '').toString();
        _edw.text = (s['edw_url'] ?? '').toString();
        _maxRows.text = s['query_max_rows'].toString();
        _timeout.text = s['query_timeout_seconds'].toString();
        _error = null;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final patch = <String, dynamic>{
        'query_max_rows': int.tryParse(_maxRows.text),
        'query_timeout_seconds': int.tryParse(_timeout.text),
      };
      if (!_badminton.text.contains('***')) patch['badminton_url'] = _badminton.text;
      if (!_edw.text.contains('***')) patch['edw_url'] = _edw.text;
      await context.read<AppState>().client!.updateSettings(patch);
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

  Future<void> _test(String url, void Function(String?) setResult) async {
    setResult('Testing…');
    try {
      final r = await context.read<AppState>().client!.testConnection(url);
      if (r['ok'] == true) {
        setResult('Connected (${r['dialect']}${r['server_version'] != null ? ' · ${r['server_version']}' : ''})');
      } else {
        setResult('Failed: ${r['error']}');
      }
    } catch (e) {
      setResult('Failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_settings == null && _error == null) {
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
          title: 'Badminton database',
          subtitle: 'MS SQL Server holding the Players / Games / PlayerQueue tables.',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _badminton,
                decoration: const InputDecoration(
                  labelText: 'SQLAlchemy URL',
                  hintText: 'mssql+pyodbc://user:pass@host:1433/Badminton?driver=ODBC+Driver+18+for+SQL+Server',
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  OutlinedButton.icon(
                    onPressed: () => _test(_badminton.text, (r) => setState(() => _badmintonTest = r)),
                    icon: const Icon(Icons.wifi_tethering, size: 16),
                    label: const Text('Test connection'),
                  ),
                  const SizedBox(width: 12),
                  if (_badmintonTest != null) Flexible(child: Text(_badmintonTest!)),
                ],
              ),
            ],
          ),
        ),
        Section(
          title: 'Enterprise data warehouse',
          subtitle: 'Any SQLAlchemy-supported on-prem warehouse (SQL Server, Postgres, Teradata, Oracle, ...).',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _edw,
                decoration: const InputDecoration(
                  labelText: 'SQLAlchemy URL',
                  hintText: 'mssql+pyodbc://user:pass@edw.local:1433/EDW?driver=ODBC+Driver+18+for+SQL+Server',
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  OutlinedButton.icon(
                    onPressed: () => _test(_edw.text, (r) => setState(() => _edwTest = r)),
                    icon: const Icon(Icons.wifi_tethering, size: 16),
                    label: const Text('Test connection'),
                  ),
                  const SizedBox(width: 12),
                  if (_edwTest != null) Flexible(child: Text(_edwTest!)),
                ],
              ),
            ],
          ),
        ),
        Section(
          title: 'Query safety',
          subtitle: 'Applied to every LLM-driven SELECT against the EDW.',
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _maxRows,
                  decoration: const InputDecoration(labelText: 'Max rows per query'),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: TextField(
                  controller: _timeout,
                  decoration: const InputDecoration(labelText: 'Query timeout (s)'),
                  keyboardType: TextInputType.number,
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
