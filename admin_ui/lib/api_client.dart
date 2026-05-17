import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException(this.status, this.message);
  final int status;
  final String message;
  @override
  String toString() => 'ApiException($status): $message';
}

class ApiClient {
  ApiClient({required this.baseUrl, required this.token});

  final String baseUrl;
  final String token;

  Uri _u(String path) => Uri.parse('$baseUrl$path');

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Future<Map<String, dynamic>> health() async {
    final r = await http.get(_u('/api/health'), headers: _headers);
    return _decodeMap(r);
  }

  Future<Map<String, dynamic>> getSettings() async {
    final r = await http.get(_u('/api/settings'), headers: _headers);
    return _decodeMap(r);
  }

  Future<Map<String, dynamic>> updateSettings(Map<String, dynamic> patch) async {
    final r = await http.put(_u('/api/settings'), headers: _headers, body: jsonEncode(patch));
    return _decodeMap(r);
  }

  Future<Map<String, dynamic>> getSkills() async {
    final r = await http.get(_u('/api/skills'), headers: _headers);
    return _decodeMap(r);
  }

  Future<Map<String, dynamic>> updateSkills(Map<String, dynamic> skills) async {
    final r = await http.put(_u('/api/skills'), headers: _headers, body: jsonEncode(skills));
    return _decodeMap(r);
  }

  Future<Map<String, dynamic>> testConnection(String url) async {
    final r = await http.post(
      _u('/api/connections/test'),
      headers: _headers,
      body: jsonEncode({'url': url}),
    );
    return _decodeMap(r);
  }

  Future<List<dynamic>> listTools() async {
    final r = await http.get(_u('/api/tools'), headers: _headers);
    return _decodeList(r);
  }

  Map<String, dynamic> _decodeMap(http.Response r) {
    _ensureOk(r);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  List<dynamic> _decodeList(http.Response r) {
    _ensureOk(r);
    return jsonDecode(r.body) as List<dynamic>;
  }

  void _ensureOk(http.Response r) {
    if (r.statusCode >= 400) {
      String message = r.body;
      try {
        final decoded = jsonDecode(r.body);
        if (decoded is Map && decoded['detail'] != null) message = decoded['detail'].toString();
      } catch (_) {}
      throw ApiException(r.statusCode, message);
    }
  }
}
