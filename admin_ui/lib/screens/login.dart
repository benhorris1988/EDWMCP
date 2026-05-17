import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api_client.dart';
import '../app_state.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late final TextEditingController _baseUrl;
  late final TextEditingController _token;
  String? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final state = context.read<AppState>();
    _baseUrl = TextEditingController(text: state.baseUrl);
    _token = TextEditingController(text: state.token);
  }

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final state = context.read<AppState>();
      await state.connect(baseUrl: _baseUrl.text, token: _token.text);
      await state.client!.health();
    } on ApiException catch (e) {
      setState(() => _error = e.message);
      await context.read<AppState>().disconnect();
    } catch (e) {
      setState(() => _error = e.toString());
      await context.read<AppState>().disconnect();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('edwmcp admin', style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 8),
                Text(
                  'Connect to the EDW + badminton MCP server',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey.shade400),
                ),
                const SizedBox(height: 32),
                TextField(
                  controller: _baseUrl,
                  decoration: const InputDecoration(
                    labelText: 'Admin API base URL',
                    hintText: 'http://127.0.0.1:8766',
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _token,
                  decoration: const InputDecoration(labelText: 'Bearer token'),
                  obscureText: true,
                ),
                const SizedBox(height: 24),
                if (_error != null) ...[
                  Text(_error!, style: const TextStyle(color: Colors.redAccent)),
                  const SizedBox(height: 16),
                ],
                FilledButton(
                  onPressed: _busy ? null : _submit,
                  child: Text(_busy ? 'Connecting…' : 'Connect'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
