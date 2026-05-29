import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'a_splash_screen.dart';
import 'transaction_item.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Hive.initFlutter();
  Hive.registerAdapter(TransactionItemAdapter());
  await Hive.openBox<TransactionItem>('transactions_box');
  await Hive.openBox<TransactionItem>('history_box');
  await Hive.openBox('userbox');
  
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: SplashScreen(),
    );
  }
}
