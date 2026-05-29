import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:intl/intl.dart';
import 'package:orlogo_zarlaga_app/j_addbill.dart';
import 'package:orlogo_zarlaga_app/k_billdetail.dart';
import 'h_connect_wall_card.dart';
import 'transaction_item.dart';
import 'e_home_page.dart';

class WalletScreen extends StatefulWidget {
  final int initialIndex;
  const WalletScreen({super.key, this.initialIndex = 0});

  @override
  State<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends State<WalletScreen> {
  late int _selectedIndex = 0;
  List<TransactionItem> transactions = [];

  @override
  void initState() {
    super.initState();
    _selectedIndex = widget.initialIndex;
    _loadStoredTransactions();
  }

  void _loadStoredTransactions() {
    final box = Hive.box<TransactionItem>('transactions_box');
    setState(() {
      transactions = box.values.toList();
      transactions.sort((a, b) => b.date.compareTo(a.date));
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF2F4F6),
      bottomNavigationBar: _bottomNav(context, 2),
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
                      colors: [Color(0xFF4BB5A1), Color(0xFF267B6E)],
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
                                onPressed: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (context) => const HomePage(),
                                    ),
                                  );
                                },       
                              ),
                              const Spacer(),
                              const Text(
                                "Түрийвч",
                                style: TextStyle(
                                  fontSize: 22,
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const Spacer(),
                              const SizedBox(width: 48),
                            ],
                          )
                        ],
                      ),
                    ),
                  ),
                ),

                Container(
                  margin: const EdgeInsets.only(top: 170),
                  width: double.infinity,
                  constraints: BoxConstraints(
                    minHeight: MediaQuery.of(context).size.height - 170,
                  ),
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.only(
                      topLeft: Radius.circular(50),
                      topRight: Radius.circular(50),
                    ),
                  ),
                  child: Column(
                    children: [
                      const SizedBox(height: 30),
                      const Text("Нийт үлдэгдэл", style: TextStyle(color: Colors.black87, fontSize: 14)),
                      const SizedBox(height: 8),
                      ValueListenableBuilder(
                        valueListenable: Hive.box<TransactionItem>('history_box').listenable(),
                        builder: (context, Box<TransactionItem> box, _) {
                          double currentBalance = box.values.fold(0, (sum, item) => sum + item.amount);
                          
                          return Text(
                            "\$${currentBalance.toStringAsFixed(2)}",
                            style: const TextStyle(
                              color: Colors.black, 
                              fontSize: 32, 
                              fontWeight: FontWeight.bold
                            ),
                          );
                        },
                      ),
                      const SizedBox(height: 20),
                      
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          _actionButton(
                            icon: Icons.add,
                            label: "Цэнэглэх",
                            onTap: () {
                              Navigator.push(
                                context,
                                  MaterialPageRoute(
                                    builder: (_)=> const ConnectCardScreen(),),
                              );
                            },
                          ),
                          const SizedBox(width: 40),
                          _actionButton(
                            icon: Icons.qr_code,
                            label: "Төлбөр нэмэх",
                            onTap: () async{
                              Navigator.push<TransactionItem>(
                                context,
                                MaterialPageRoute(
                                  builder: (_)=> const AddExpensePage(),),
                              );
                            },
                          ),
                        ],
                      ),
                      
                      const SizedBox(height: 10),
                      _transactionTabs(),
                      
                      
                      _selectedIndex == 0 
                          ? _transactionList() 
                          : _pendingTransactionList(),
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

  Widget _transactionTabs() {
    double width = MediaQuery.of(context).size.width - 40;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
      child: Container(
        height: 55,
        decoration: BoxDecoration(
          color: Colors.grey[200],
          borderRadius: BorderRadius.circular(30),
        ),
        child: Stack(
          children: [
            AnimatedAlign(
              alignment: _selectedIndex == 0 ? Alignment.centerLeft : Alignment.centerRight,
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeInOut,
              child: Container(
                width: width / 2,
                height: 45,
                margin: const EdgeInsets.all(5),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(30),
                  boxShadow: [BoxShadow(color: Colors.black12, blurRadius: 4)],
                ),
              ),
            ),
            Row(
              children: [
                _tabItem("Гүйлгээнүүд", 0),
                _tabItem("Хүлээгдэж буй", 1),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _tabItem(String title, int index) {
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedIndex = index),
        child: Container(
          alignment: Alignment.center,
          color: Colors.transparent,
          child: Text(
            title,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: _selectedIndex == index ? Colors.black : Colors.grey,
            ),
          ),
        ),
      ),
    );
  }

  Widget _transactionList() {
    return ValueListenableBuilder(
      valueListenable: Hive.box<TransactionItem>('history_box').listenable(),
      builder: (context, Box<TransactionItem> box, _) {
        final history = box.values.toList().reversed.toList();
        final keys = box.keys.toList().reversed.toList();

        if (history.isEmpty) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Text("Гүйлгээний түүх хоосон байна."),
            ),
          );
        }

        return ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: history.length,
          itemBuilder: (context, index) {
            final item = history[index];
            final itemKey = keys[index];
            bool isIncome = item.amount > 0; 

            return ListTile(
              onTap: () => _showDeleteDialog(context, itemKey, item.service, true),
              leading: CircleAvatar(
                backgroundColor: isIncome ? const Color.fromARGB(255, 176, 225, 178) : const Color.fromARGB(255, 199, 100, 91).withOpacity(0.1),
                child: Icon(
                  isIncome ? Icons.arrow_downward : Icons.arrow_upward,
                  color: isIncome ? const Color.fromARGB(255, 27, 112, 30) : Colors.red,
                ),
              ),
              title: Text(
                item.service,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              subtitle: Text(DateFormat('yyyy-MM-dd').format(item.date)),
              trailing: Text(
                "${isIncome ? '+' : '-'} \$${item.amount.abs().toStringAsFixed(2)}",
                style: TextStyle(
                  color: isIncome ? Colors.green : Colors.red,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),
            );
          },
        );
      },
    );
  }


  Widget _pendingTransactionList() {
    return ValueListenableBuilder(
      valueListenable: Hive.box<TransactionItem>('transactions_box').listenable(),
      builder: (context, Box<TransactionItem> box, _) {
        final transactions = box.values.toList().reversed.toList();
        final keys = box.keys.toList().reversed.toList();

        if (transactions.isEmpty) {
          return const Center(child: Text("Одоогоор төлбөр байхгүй байна."));
        }

        return ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: transactions.length,
          itemBuilder: (context, index) {
            final item = transactions[index];
            final itemKey = keys[index];
            return _transactionTile2(context, item, index, itemKey);
          },
        );
      },
    );
  }


  Widget _transactionTile2(BuildContext context, TransactionItem tx, int index, dynamic itemKey) {
    return ListTile(
      onTap: () => _showDeleteDialog(context, itemKey, tx.service, false),
      leading: const CircleAvatar(
        backgroundColor: Colors.teal, 
        child: Icon(Icons.receipt_long, color: Colors.white)
      ),
      title: Text(tx.service),
      subtitle: Text(DateFormat('EEE, dd MMM yyyy').format(tx.date)),
      trailing: ElevatedButton(
        onPressed: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => BillDetailsScreen(transaction: tx), 
            ),
          );
        },
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.teal,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
        child: const Text("Төлөх", style: TextStyle(color: Colors.white)),
      ),
    );
  }

  Widget _actionButton({required IconData icon, required String label, required VoidCallback onTap}) {
    return Column(
      children: [
        GestureDetector(
          onTap: onTap,
          child: Container(
            width: 60, height: 60,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: const Color(0xFF267B6E), width: 1.5),
            ),
            child: Icon(icon, color: const Color(0xFF267B6E), size: 28),
          ),
        ),
        const SizedBox(height: 8),
        Text(label, style: const TextStyle(color: Color(0xFF267B6E), fontSize: 12, fontWeight: FontWeight.w600)),
      ],
    );
  }

  Widget _bottomNav(BuildContext context, int currentIndex) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 18),
      decoration: const BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black12,
            blurRadius: 10,
            offset: Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [

          InkWell(
            onTap: () {
              if (currentIndex != 0) {
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (_) => const HomePage()),
                  
                );
              }
            },
            child: Icon(
              Icons.home,
              color: currentIndex == 0 ? Colors.teal : Colors.grey,
              size: 30,
            ),
          ),

          InkWell(
            onTap: () {
              //
            },
            child: Icon(
              Icons.bar_chart,
              color: currentIndex == 1 ? Colors.teal : Colors.grey,
              size: 30,
            ),
          ),

          InkWell(
            onTap: () {
              if (currentIndex != 2) {
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (_) => const WalletScreen()),
                );
              }
            },
            child: Icon(
              Icons.account_balance_wallet,
              color: currentIndex == 2 ? Colors.teal : Colors.grey,
              size: 30,
            ),
          ),

          InkWell(
            onTap: () {
              //
            },
            child: Icon(
              Icons.person,
              color: currentIndex == 3 ? Colors.teal : Colors.grey,
              size: 30,
            ),
          ),
        ],
      ),
    );
  }

  void _showDeleteDialog(BuildContext context, dynamic itemKey, String serviceName, bool isHistory) {
    showDialog(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: const Text("Устгах"),
          content: Text("'$serviceName' гүйлгээг устгах уу?"),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext), 
              child: const Text("Цуцлах")
            ),
            TextButton(
              onPressed: () async {
                final boxName = isHistory ? 'history_box' : 'transactions_box';
                final box = Hive.box<TransactionItem>(boxName);
                await box.delete(itemKey);
                
                if (dialogContext.mounted) {
                  Navigator.pop(dialogContext);
                }
              },
              child: const Text("Устгах", style: TextStyle(color: Colors.red)),
            ),
          ],
        );
      },
    );
  }
}