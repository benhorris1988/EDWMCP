import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../widgets/section.dart';

class BadmintonScreen extends StatefulWidget {
  const BadmintonScreen({super.key});

  @override
  State<BadmintonScreen> createState() => _BadmintonScreenState();
}

class _BadmintonScreenState extends State<BadmintonScreen> {
  Map<String, dynamic>? _skills;
  String? _error;
  bool _saving = false;

  final _ctrls = <String, TextEditingController>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _setCtrl(String key, String value) {
    _ctrls.putIfAbsent(key, () => TextEditingController()).text = value;
  }

  Future<void> _load() async {
    try {
      final s = await context.read<AppState>().client!.getSkills();
      setState(() {
        _skills = s;
        final b = (s['badminton'] as Map).cast<String, dynamic>();
        _setCtrl('schema', (b['schema'] ?? '').toString());
        final tables = (b['tables'] as Map).cast<String, dynamic>();
        tables.forEach((k, v) => _setCtrl('table.$k', v.toString()));
        final columns = (b['columns'] as Map).cast<String, dynamic>();
        columns.forEach((tableKey, cols) {
          (cols as Map).cast<String, dynamic>().forEach((c, v) {
            _setCtrl('col.$tableKey.$c', (v ?? '').toString());
          });
        });
        final rot = (b['rotation'] as Map).cast<String, dynamic>();
        _setCtrl('rot.players_per_game', rot['players_per_game'].toString());
        _setCtrl('rot.rest_minutes', rot['rest_minutes'].toString());
        _setCtrl('rot.strategy', rot['strategy'].toString());
        _error = null;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Map<String, dynamic> _buildPayload() {
    final s = Map<String, dynamic>.from(_skills!);
    final b = Map<String, dynamic>.from(s['badminton'] as Map);
    b['schema'] = _ctrls['schema']!.text.isEmpty ? null : _ctrls['schema']!.text;

    final tables = Map<String, dynamic>.from(b['tables'] as Map);
    tables.updateAll((k, _) => _ctrls['table.$k']!.text);
    b['tables'] = tables;

    final columns = Map<String, dynamic>.from(b['columns'] as Map);
    columns.forEach((tableKey, cols) {
      final updated = Map<String, dynamic>.from(cols as Map);
      updated.updateAll((c, _) {
        final v = _ctrls['col.$tableKey.$c']?.text ?? '';
        return v.isEmpty ? null : v;
      });
      columns[tableKey] = updated;
    });
    b['columns'] = columns;

    final rot = Map<String, dynamic>.from(b['rotation'] as Map);
    rot['players_per_game'] = int.tryParse(_ctrls['rot.players_per_game']!.text) ?? rot['players_per_game'];
    rot['rest_minutes'] = int.tryParse(_ctrls['rot.rest_minutes']!.text) ?? rot['rest_minutes'];
    rot['strategy'] = _ctrls['rot.strategy']!.text;
    b['rotation'] = rot;

    s['badminton'] = b;
    return s;
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await context.read<AppState>().client!.updateSkills(_buildPayload());
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
    if (_skills == null) {
      return Center(child: Text(_error ?? '', style: const TextStyle(color: Colors.redAccent)));
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
          title: 'Schema',
          subtitle: 'Optional schema prefix (e.g. "dbo" for SQL Server). Leave blank for none.',
          child: TextField(controller: _ctrls['schema'], decoration: const InputDecoration(labelText: 'Schema')),
        ),
        Section(
          title: 'Table names',
          subtitle: 'Map the logical tables the badminton skill needs to your actual table names.',
          child: Column(
            children: [
              for (final key in ['players', 'courts', 'games', 'game_players', 'queue'])
                _row(key, _ctrls['table.$key']!),
            ],
          ),
        ),
        for (final entry in _columnsByTable())
          Section(
            title: 'Columns: ${entry.tableLabel}',
            child: Column(children: [for (final c in entry.fields) _row(c.label, _ctrls['col.${entry.tableKey}.${c.key}']!)]),
          ),
        Section(
          title: 'Rotation rules',
          subtitle: 'How suggest_next_players picks the next group from the queue.',
          child: Column(
            children: [
              _row('Players per game', _ctrls['rot.players_per_game']!),
              _row('Rest period (minutes)', _ctrls['rot.rest_minutes']!),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(width: 200, child: Text('Strategy', style: TextStyle(color: Colors.grey.shade400))),
                    Expanded(
                      child: DropdownButton<String>(
                        isExpanded: true,
                        value: _ctrls['rot.strategy']!.text,
                        items: const [
                          DropdownMenuItem(value: 'queue_order', child: Text('queue_order')),
                          DropdownMenuItem(value: 'balanced_skill', child: Text('balanced_skill')),
                        ],
                        onChanged: (v) => setState(() => _ctrls['rot.strategy']!.text = v ?? 'balanced_skill'),
                      ),
                    ),
                  ],
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

  Widget _row(String label, TextEditingController c) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(width: 200, child: Text(label, style: TextStyle(color: Colors.grey.shade400))),
          Expanded(child: TextField(controller: c, decoration: const InputDecoration(isDense: true))),
        ],
      ),
    );
  }

  Iterable<_TableColumns> _columnsByTable() sync* {
    yield const _TableColumns('players', 'Players', [
      _Field('id', 'id'),
      _Field('name', 'name'),
      _Field('skill', 'skill rating'),
      _Field('active', 'active flag'),
      _Field('joined_at', 'joined timestamp'),
    ]);
    yield const _TableColumns('courts', 'Courts', [
      _Field('id', 'id'),
      _Field('name', 'name'),
      _Field('available', 'available flag'),
    ]);
    yield const _TableColumns('games', 'Games', [
      _Field('id', 'id'),
      _Field('court_id', 'court id'),
      _Field('started_at', 'started at'),
      _Field('ended_at', 'ended at'),
      _Field('status', 'status'),
      _Field('winning_team', 'winning team'),
    ]);
    yield const _TableColumns('game_players', 'GamePlayers', [
      _Field('game_id', 'game id'),
      _Field('player_id', 'player id'),
      _Field('team', 'team'),
    ]);
    yield const _TableColumns('queue', 'PlayerQueue', [
      _Field('player_id', 'player id'),
      _Field('joined_at', 'joined at'),
    ]);
  }
}

class _TableColumns {
  const _TableColumns(this.tableKey, this.tableLabel, this.fields);
  final String tableKey;
  final String tableLabel;
  final List<_Field> fields;
}

class _Field {
  const _Field(this.key, this.label);
  final String key;
  final String label;
}
