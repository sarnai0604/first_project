import 'package:hive/hive.dart';

part 'transaction_item.g.dart';

@HiveType(typeId: 0)
class TransactionItem extends HiveObject {
  @HiveField(0)
  final String id;

  @HiveField(1)
  final String service;

  @HiveField(2)
  final double amount;

  @HiveField(3)
  final DateTime date;

  TransactionItem({
    required this.id,
    required this.service,
    required this.amount,
    required this.date,
  });
}