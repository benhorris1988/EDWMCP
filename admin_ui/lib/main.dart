import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_state.dart';
import 'screens/dashboard.dart';
import 'screens/login.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final state = AppState();
  await state.hydrate();
  runApp(
    ChangeNotifierProvider.value(value: state, child: const EdwmcpAdminApp()),
  );
}

class EdwmcpAdminApp extends StatelessWidget {
  const EdwmcpAdminApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'edwmcp admin',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal, brightness: Brightness.dark),
        scaffoldBackgroundColor: const Color(0xFF0f1115),
        cardTheme: CardThemeData(
          color: const Color(0xFF181b22),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          isDense: true,
        ),
      ),
      home: Consumer<AppState>(
        builder: (context, state, _) {
          if (!state.isHydrated) {
            return const Scaffold(body: Center(child: CircularProgressIndicator()));
          }
          return state.isAuthenticated ? const DashboardScreen() : const LoginScreen();
        },
      ),
    );
  }
}
