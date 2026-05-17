import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';
import '../widgets/section.dart';
import 'connections.dart';
import 'badminton.dart';
import 'edw_config.dart';
import 'tools.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> with SingleTickerProviderStateMixin {
  late final TabController _tab;
  Map<String, dynamic>? _health;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 5, vsync: this);
    _load();
  }

  Future<void> _load() async {
    try {
      final c = context.read<AppState>().client!;
      final h = await c.health();
      setState(() {
        _health = h;
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('edwmcp admin'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh status',
            onPressed: _load,
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Disconnect',
            onPressed: () => context.read<AppState>().disconnect(),
          ),
        ],
        bottom: TabBar(
          controller: _tab,
          isScrollable: true,
          tabs: const [
            Tab(text: 'Overview'),
            Tab(text: 'Connections'),
            Tab(text: 'Badminton'),
            Tab(text: 'EDW'),
            Tab(text: 'Tools'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tab,
        children: [
          _OverviewTab(health: _health, error: _error),
          const ConnectionsScreen(),
          const BadmintonScreen(),
          const EdwScreen(),
          const ToolsScreen(),
        ],
      ),
    );
  }
}

class _OverviewTab extends StatelessWidget {
  const _OverviewTab({required this.health, required this.error});

  final Map<String, dynamic>? health;
  final String? error;

  @override
  Widget build(BuildContext context) {
    if (error != null) {
      return Center(child: Text(error!, style: const TextStyle(color: Colors.redAccent)));
    }
    if (health == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final h = health!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Section(
          title: 'Server',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              KeyValueRow('Status', h['status'].toString()),
              KeyValueRow('Version', h['version'].toString()),
              KeyValueRow('Transport', h['transport'].toString()),
              KeyValueRow('Demo mode', h['demo'].toString()),
              KeyValueRow('Config path', h['config_path'].toString()),
            ],
          ),
        ),
        Section(
          title: 'Data sources',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _BoolRow('Badminton DB configured', h['badminton_configured'] == true),
              _BoolRow('EDW configured', h['edw_configured'] == true),
            ],
          ),
        ),
      ],
    );
  }
}

class _BoolRow extends StatelessWidget {
  const _BoolRow(this.label, this.ok);

  final String label;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(
            ok ? Icons.check_circle : Icons.error_outline,
            color: ok ? Colors.greenAccent : Colors.amber,
            size: 18,
          ),
          const SizedBox(width: 8),
          Text(label),
        ],
      ),
    );
  }
}
