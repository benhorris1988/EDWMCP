import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

class AppState extends ChangeNotifier {
  AppState();

  static const _kBaseUrl = 'edwmcp.baseUrl';
  static const _kToken = 'edwmcp.token';

  String baseUrl = 'http://127.0.0.1:8766';
  String token = '';
  bool _hydrated = false;
  ApiClient? _client;

  ApiClient? get client => _client;
  bool get isAuthenticated => _client != null;
  bool get isHydrated => _hydrated;

  Future<void> hydrate() async {
    final prefs = await SharedPreferences.getInstance();
    baseUrl = prefs.getString(_kBaseUrl) ?? baseUrl;
    token = prefs.getString(_kToken) ?? '';
    if (token.isNotEmpty) {
      _client = ApiClient(baseUrl: baseUrl, token: token);
    }
    _hydrated = true;
    notifyListeners();
  }

  Future<void> connect({required String baseUrl, required String token}) async {
    this.baseUrl = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    this.token = token.trim();
    _client = ApiClient(baseUrl: this.baseUrl, token: this.token);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kBaseUrl, this.baseUrl);
    await prefs.setString(_kToken, this.token);
    notifyListeners();
  }

  Future<void> disconnect() async {
    _client = null;
    token = '';
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kToken);
    notifyListeners();
  }
}
