import 'package:flutter/material.dart';
import 'package:orlogo_zarlaga_app/f_wallet.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:intl/intl.dart';
import 'transaction_item.dart';


void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: const HomePage(),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context){
    return Scaffold(
      backgroundColor: const Color(0xFFF2F4F6),

      bottomNavigationBar: _bottomNav(context, 0),
      
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
                      bottomLeft: Radius.circular(100),
                      bottomRight: Radius.circular(100),
                    ),
                  ),
                ),
               
                Positioned(
                  top: 70,
                  left: 20,
                  right: 0,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      Text(
                        "Өглөөний мэнд!",
                        style: TextStyle(
                          fontSize: 20,
                          color: Colors.white),
                        ),
                        SizedBox(height: 5),
                        Text("Сарнай",
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 26,
                          fontWeight: FontWeight.bold),
                        )
                      ],
                    ),
                  ),
                 
                Positioned(
                  top: 140,
                  left: 20,
                  right: 20,
                  child: _balanceCard(),
                ),
              ],
            ),
            const SizedBox(height: 100),
            _transactionSection(),
            const SizedBox(height: 20),
            _sendAgainSection(),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _balanceCard() {
    return ValueListenableBuilder(
      valueListenable: Hive.box<TransactionItem>('history_box').listenable(),
      builder: (context, Box<TransactionItem> box, _) {
        double income = 0;
        double expense = 0;

        for (var item in box.values) {
          if (item.amount > 0) {
            income += item.amount;
          } else {
            expense += item.amount.abs();
          }
        }
        double balance = income - expense;

        return Container(
          margin: const EdgeInsets.only(bottom: 20),
          padding: const EdgeInsets.all(25),
          decoration: BoxDecoration(
            color: const Color(0xFF267B6E),
            borderRadius: BorderRadius.circular(25),
            boxShadow: const [
              BoxShadow(color: Colors.black26, blurRadius: 10, offset: Offset(0, 5)),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("Нийт үлдэгдэл",
                  style: TextStyle(color: Colors.white70, fontSize: 14)),
              const SizedBox(height: 10),
              Text(
                "\$${balance.toStringAsFixed(2)}",
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 32,
                    fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _amountInfo("Орлого", income, Icons.arrow_downward, Colors.greenAccent),
                  _amountInfo("Зарлага", expense, Icons.arrow_upward, Colors.orangeAccent),
                ],
              )
            ],
          ),
        );
      },
    );
  }

  Widget _amountInfo(String label, double amount, IconData icon, Color iconColor) {
    return Column(
      crossAxisAlignment: label == "Орлого" ? CrossAxisAlignment.start : CrossAxisAlignment.end,
      children: [
        Row(
          children: [
            Icon(icon, color: iconColor, size: 14),
            const SizedBox(width: 4),
            Text(label, style: const TextStyle(color: Colors.white70)),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          "\$${amount.toStringAsFixed(2)}",
          style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w500),
        ),
      ],
    );
  }

  Widget _transactionSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              Text("Гүйлгээний түүх",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 15),       
          Container(
            height: 330,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
            ),
            child: ValueListenableBuilder(
              valueListenable: Hive.box<TransactionItem>('history_box').listenable(),
              builder: (context, Box<TransactionItem> box, _) {
                final history = box.values.toList().reversed.toList();

                if (history.isEmpty) {
                  return const Center(child: Text("Түүх хоосон байна."));
                }

                return ListView.builder(
                  padding: const EdgeInsets.all(10),
                  itemCount: history.length,
                  itemBuilder: (context, index) {
                    final item = history[index];
                    return _transactionTile(item);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _transactionTile(TransactionItem item) {
    bool isIncome = item.amount > 0;

    return Container(
      margin: const EdgeInsets.only(bottom: 15),
      child: Row(
        children: [
          CircleAvatar(
            radius: 22,
            backgroundColor: isIncome ? const Color.fromARGB(255, 176, 225, 178) : const Color.fromARGB(255, 180, 94, 86).withOpacity(0.1),
            child: Icon(
              isIncome ? Icons.arrow_downward : Icons.arrow_upward,
              color: isIncome ? const Color.fromARGB(255, 44, 123, 46) : Colors.red,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(item.service,
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.bold)),
              Text(DateFormat('MMM dd, yyyy').format(item.date), 
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
            ],
          ),
          const Spacer(),
          Text(
            "${isIncome ? '+' : '-'} \$${item.amount.abs().toStringAsFixed(2)}",
            style: TextStyle(
              color: isIncome ? Colors.green : Colors.red,
              fontWeight: FontWeight.bold,
              fontSize: 15,
            ),
          ),
        ],
      ),
    );
  }

  Widget _sendAgainSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              Text("Send Again",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              Text("See all", style: TextStyle(color: Colors.grey)),
            ],
          ),
        ),
        const SizedBox(height: 10),

        SizedBox(
          height: 70,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 20),
            children: [
              _profileCircle("assets/images/p1.jpg"),
              _profileCircle("assets/images/p2.jpg"),
              _profileCircle("assets/images/p3.jpg"),
              _profileCircle("assets/images/p4.jpg"),
              _profileCircle("assets/images/p5.jpg"),
            ],
          ),
        ),
      ],
    );
  }

  Widget _profileCircle(String img) {
    return Container(
      margin: const EdgeInsets.only(right: 12),
      child: CircleAvatar(
        radius: 28,
        backgroundImage: AssetImage(img),
      ),
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
                Navigator.pushAndRemoveUntil(
                  context,
                  MaterialPageRoute(builder: (_) => const HomePage()),
                  (route) => false,
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
}