import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'f_wallet.dart';
import 'transaction_item.dart';
import 'package:qr_flutter/qr_flutter.dart';

// BILL DETAILS SCREEN
class BillDetailsScreen extends StatefulWidget {
  final TransactionItem transaction;

  const BillDetailsScreen({super.key, required this.transaction});

  @override
  State<BillDetailsScreen> createState() => _BillDetailsScreenState();
}

class _BillDetailsScreenState extends State<BillDetailsScreen> {
  int selectedMethod = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF2F4F6),
      body: Stack(
        children: [
          _topGradient('Төлбөр төлөх', context),
          _whiteBody(
            child: Column(
              children: [
                _billCard(
                  serviceName: widget.transaction.service,
                  amount: widget.transaction.amount,
                ),
                const SizedBox(height: 30),
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text("Төлбөрийн хэрэгсэл", 
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                ),
                const SizedBox(height: 10),
                _methodTile('Дебит карт', 0, Icons.credit_card),
                _methodTile('Paypal', 1, Icons.account_balance_wallet),
                const Spacer(),
                _mainButton('ҮРГЭЛЖЛҮҮЛЭХ', () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => BillPaymentScreen(transaction: widget.transaction)),
                  );
                }, isPrimary: true)
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _methodTile(String title, int index, IconData icon) {
    return GestureDetector(
      onTap: () => setState(() => selectedMethod = index),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: selectedMethod == index ? const Color(0xFFE8F6F3) : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selectedMethod == index ? Colors.teal : Colors.grey.shade300,
            width: 1,
          ),
        ),
        child: Row(
          children: [
            Icon(icon, color: selectedMethod == index ? Colors.teal : Colors.grey),
            const SizedBox(width: 12),
            Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w500))),
            Radio(
              value: index,
              groupValue: selectedMethod,
              activeColor: Colors.teal,
              onChanged: (int? value) => setState(() => selectedMethod = value!),
            ),
          ],
        ),
      ),
    );
  }
}


class BillPaymentScreen extends StatelessWidget {
  final TransactionItem transaction;
  const BillPaymentScreen({super.key, required this.transaction});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF2F4F6),
      body: Stack(
        children: [
          _topGradient('Баталгаажуулах', context),
          _whiteBody(
            child: Column(
              children: [
                const SizedBox(height: 20),
                const Text("Та энэ төлбөрийг төлөхдөө итгэлтэй байна уу?"),
                const SizedBox(height: 20),
                _billCard(
                  serviceName: transaction.service,
                  amount: transaction.amount,
                ),
                const Spacer(),
                _mainButton('БАТАЛГААЖУУЛАХ', () {
                  Navigator.pushReplacement( 
                    context,
                    MaterialPageRoute(
                        builder: (_) => BillResultScreen(transaction: transaction)),
                  );
                }, isPrimary: true),
                const SizedBox(height: 10),
                _mainButton('ЦУЦЛАХ', () => Navigator.pop(context), isPrimary: false),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class BillResultScreen extends StatelessWidget {
  final TransactionItem transaction;
  const BillResultScreen({super.key, required this.transaction});

  @override
  Widget build(BuildContext context) {
    final String txnId = 'TXN${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}';
    return Scaffold(
      backgroundColor: const Color(0xFFF2F4F6),
      body: Stack(
        children: [
          _topGradient('Төлбөрийн үр дүн', context, showBack: false),
          _whiteBody(
            child: Column(
              children: [
                const Center(
                  child: Column(
                    children: [
                      Icon(Icons.check_circle, size: 80, color: Colors.teal),
                      SizedBox(height: 10),
                      Text('Амжилттай төлөгдлөө',
                          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
                const SizedBox(height: 30),
                _infoRow('Үйлчилгээ', transaction.service),
                _infoRow('Төлөв', 'Амжилттай', valueColor: Colors.green),
                _infoRow('Огноо', DateFormat('yyyy-MM-dd HH:mm').format(DateTime.now())),
                _infoRow('Гүйлгээний №', 'TXN${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}'),
                const Divider(height: 40),
                _infoRow('Нийт төлсөн', '\$${(transaction.amount + 1).toStringAsFixed(2)}', bold: true),


                const SizedBox(height: 20),
                const Text("Цахим баримт (QR)", style: TextStyle(color: Colors.grey, fontSize: 13)),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: QrImageView(
                    data: 'Service: ${transaction.service}\nID: $txnId\nAmount: ${(transaction.amount + 1)}',
                    version: QrVersions.auto,
                    size: 150.0,
                    gapless: false,
                    eyeStyle: const QrEyeStyle(
                      eyeShape: QrEyeShape.square,
                      color: Color(0xFF267B6E),
                    ),
                    dataModuleStyle: const QrDataModuleStyle(
                      dataModuleShape: QrDataModuleShape.square,
                      color: Color(0xFF267B6E),
                    ),
                  ),
                ),
                const SizedBox(height: 30),
                _mainButton("ДУУСГАХ",() async {
                    final historyBox = Hive.box<TransactionItem>('history_box');
                    final pendingBox = Hive.box<TransactionItem>('transactions_box');

                    await historyBox.add(TransactionItem( //zarlaga
                      id: transaction.id,
                      service: transaction.service,
                      amount: -(transaction.amount.abs()),
                      date: DateTime.now(),
                    ));

                    final keyToDelete = pendingBox.keys.firstWhere(
                      (k) => pendingBox.get(k)?.id == transaction.id,
                      orElse: () => null,
                    );

                    if (keyToDelete != null) {
                      await pendingBox.delete(keyToDelete);
                    }

                    if (context.mounted) {
                      Navigator.of(context).pushAndRemoveUntil(
                        MaterialPageRoute(builder: (context) => const WalletScreen()),
                        (route) => false,
                      );
                    }
                  }, 
                  isPrimary: true,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


Widget _topGradient(String title, BuildContext context, {bool showBack = true}) {
  return Container(
    height: 250,
    width: double.infinity,
    decoration: const BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF4BB5A1), Color(0xFF267B6E)],
      ),
    ),
    child: SafeArea(
      child: Column(
        children: [
          const SizedBox(height: 60),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10),
            child: Row(
              children: [
                if (showBack)
                  IconButton(
                    icon: const Icon(Icons.arrow_back_ios_new, color: Colors.white, size: 22),
                    onPressed: () => Navigator.pop(context),
                  )
                else
                  const SizedBox(width: 48),
                
                Expanded(
                  child: Text(
                    title,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 20, 
                      color: Colors.white, 
                      fontWeight: FontWeight.bold
                    ),
                  ),
                ),
                const SizedBox(width: 48), 
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

Widget _mainButton(String text, VoidCallback onTap, {required bool isPrimary}) {
  return SizedBox(
    width: double.infinity,
    height: 55,
    child: ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: isPrimary ? const Color(0xFF267B6E) : Colors.white,
        foregroundColor: isPrimary ? Colors.white : Colors.teal,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(30),
          side: const BorderSide(color: Color(0xFF267B6E)),
        ),
      ),
      onPressed: onTap,
      child: Text(text, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
    ),
  );
}

Widget _infoRow(String label, String value, {bool bold = false, Color? valueColor}) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(color: Colors.grey.shade600, fontSize: 15)),
        Text(value, style: TextStyle(
          fontWeight: bold ? FontWeight.bold : FontWeight.w500,
          fontSize: 15,
          color: valueColor ?? Colors.black87,
        )),
      ],
    ),
  );
}


Widget _whiteBody({required Widget child}) {
  return Container(
    margin: const EdgeInsets.only(top: 170),
    padding: const EdgeInsets.all(20),
    decoration: const BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.only(
        topLeft: Radius.circular(50),
        topRight: Radius.circular(50),
      ),
    ),
    child: child,
  );
}

Widget _billCard({required String serviceName, required double amount}) {
  double fee = 1;
  return Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(20),
      boxShadow: const [BoxShadow(color: Colors.black12, blurRadius: 8)],
    ),
    child: Column(
      children: [
        const CircleAvatar(
          backgroundColor: Color(0xFFE8F6F3),
          child: Icon(Icons.receipt_long, color: Colors.teal),
        ),
        const SizedBox(height: 10),
        Text(serviceName, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        const SizedBox(height: 20),
        _priceRow('Үнэ', '\$${amount.toStringAsFixed(2)}'),
        _priceRow('Хураамж', '\$${fee.toStringAsFixed(2)}'),
        const Divider(height: 20),
        _priceRow('Нийт', '\$${(amount + fee).toStringAsFixed(2)}', bold: true),
      ],
    ),
  );
}


class _priceRow extends StatelessWidget {
  final String label;
  final String value;
  final bool bold;

  const _priceRow(this.label, this.value, {this.bold = false});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label),
        Text(value,
            style: TextStyle(fontWeight: bold ? FontWeight.bold : null)),
      ],
    );
  }
}
