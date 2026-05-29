import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:hive/hive.dart';
import 'transaction_item.dart';
import 'f_wallet.dart';


class AddExpensePage extends StatefulWidget {
  const AddExpensePage({super.key});

  @override
  State<AddExpensePage> createState() => _AddExpensePageState();
}

class _AddExpensePageState extends State<AddExpensePage> {
  final TextEditingController _amountController = TextEditingController();
  DateTime selectedDate = DateTime.now();
  String selectedService = 'Netflix';

  final List<Map<String, String>> services = [
    {'name': 'Netflix', 'icon': 'assets/icons/netflix.png'},
    {'name': 'Spotify', 'icon': 'assets/icons/spotify.png'},
    {'name': 'YouTube', 'icon': 'assets/icons/youtube.png'},
    {'name': 'TV', 'icon': 'assets/icons/tv.png'},
    {'name': 'Electrecity', 'icon': 'assets/icons/electricity.png'},
  ];

  Future<void> _selectDate(BuildContext context) async {
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: selectedDate,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );

    if (picked != null && picked != selectedDate) {
      setState(() => selectedDate = picked);
    }
  }


  void _saveTransaction() async {
    final amountText = _amountController.text;
    final amount = double.tryParse(amountText);

    if (amountText.isEmpty || amount == null || amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Зөв үнийн дүн оруулна уу!')),
      );
      return;
    }

    final newTransaction = TransactionItem(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      service: selectedService,
      amount: -amount,
      date: selectedDate,
    );

    final box = Hive.box<TransactionItem>('transactions_box');
    await box.put(newTransaction.id, newTransaction);

    if (!mounted) return;
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(
        builder: (context) => const WalletScreen(initialIndex: 1), // 1-р таб буюу "Хүлээгдэж буй"
      ),
      (route) => false,
    );
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SingleChildScrollView(
        child: Column(
          children: [
            Stack(
              clipBehavior: Clip.none,
              children: [
                Container(
                  height: 250,
                  width: double.infinity,
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        Color(0xFF4BB5A1),
                        Color(0xFF267B6E),
                      ],
                    ),
                    borderRadius: BorderRadius.only(
                      bottomLeft: Radius.circular(50),
                      bottomRight: Radius.circular(50),
                    ),
                  ),
                  child: SafeArea(
                      child: Padding(
                        padding: const EdgeInsets.only(top: 60),
                        child: Column(
                          children: [
                            Row(
                              children: [
                                IconButton(
                                  icon: const Icon(Icons.arrow_back, color: Colors.white),
                                  onPressed: () => Navigator.pop(context),
                                ),
                                const Spacer(),
                                const Text(
                                  "Төлбөр нэмэх",
                                  style: TextStyle(
                                    fontSize: 22,
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                const Spacer(),
                                const SizedBox(width: 48),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),

          
            Container(
              margin: const EdgeInsets.only(top: 180, left: 25, right: 25),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.all(Radius.circular(30)
                ),
              ),
              child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Үйлчилгээ сонгох', style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 10),
                      DropdownButtonFormField<String>(
                        value: selectedService,
                        decoration: InputDecoration(
                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        items: services.map((service) {
                          return DropdownMenuItem<String>(
                            value: service['name'],
                            child: Row(
                              children: [
                                Image.asset(
                                  service['icon']!,
                                  width: 24,
                                  height: 24,
                                  errorBuilder: (context, error, stackTrace) => 
                                      const Icon(Icons.category, size: 24), // Зураг олдохгүй бол харуулах дүрс
                                ),
                                const SizedBox(width: 15),
                                Text(service['name']!),
                              ],
                            ),
                          );
                        }).toList(),
                        onChanged: (value) => setState(() => selectedService = value!),
                      ),
                      
                      const SizedBox(height: 20),
                      const Text('Үнийн дүн', style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _amountController,
                        keyboardType: TextInputType.number,
                        decoration: InputDecoration(
                          prefixIcon: const Icon(Icons.attach_money),
                          hintText: "0.00",
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                      
                      const SizedBox(height: 20),
                      const Text('Огноо', style: TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 10),
                      InkWell(
                        onTap: () => _selectDate(context),
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.grey),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.calendar_today, size: 18, color: Colors.teal),
                              const SizedBox(width: 10),
                              Text(DateFormat('yyyy-MM-dd').format(selectedDate)),
                            ],
                          ),
                        ),
                      ),
                      
                      const SizedBox(height: 30),
                      ElevatedButton(
                        onPressed: _saveTransaction,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF267B6E),
                          minimumSize: const Size.fromHeight(55),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                        ),
                        child: const Text(
                          'Нэмэх',
                          style: TextStyle(fontSize: 16, color: Colors.white, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}


