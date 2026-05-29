import 'package:flutter/material.dart';
import 'e_home_page.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'f_wallet.dart';
import 'transaction_item.dart';

class ConnectCardScreen extends StatefulWidget {
  const ConnectCardScreen({super.key});

  @override
  State<ConnectCardScreen> createState() => _CardScreenState();
}

class _CardScreenState extends State<ConnectCardScreen> {
  int _selectedIndex = 0;

  final TextEditingController _amountController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final double width = MediaQuery.of(context).size.width;

    return Scaffold(
      backgroundColor: const Color(0xFFF2F4F6),
      bottomNavigationBar: _bottomNav(context, 2),

      body: Stack(
        children: [
          Container(
            height: 250,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFF4BB5A1),
                  Color(0xFF267B6E),
                ],
              ),
            ),

            child: SafeArea(child: 
            Padding(padding: const EdgeInsets.only(top: 60),
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
                        "Түрийвч цэнэглэх",
                        style: TextStyle(
                          fontSize: 20,
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
            margin: const EdgeInsets.only(top: 140),
            width: double.infinity,
            height: 750,
            padding: const EdgeInsets.all(20),
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(50),
                topRight: Radius.circular(50),
              ),
            ),
            child: Column(
              children: [
                Container(
                  height: 50,
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(30),
                    ),
                    child: Stack(
                      children: [
                        AnimatedAlign(
                          alignment: _selectedIndex == 0
                              ? Alignment.centerLeft
                              : Alignment.centerRight,
                          duration: const Duration(milliseconds: 250),
                          child: Container(
                            width: width / 2,
                            height: 40,
                            margin: const EdgeInsets.all(5),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(30),
                            ),
                          ),
                        ),
                        Row(
                          children: [
                            _tabButton("Картууд", 0),
                            _tabButton("Аккаунт", 1),
                          ],
                        )
                      ],
                    ),
                  ),

                  const SizedBox(height: 20),

                  Expanded(
                    child: SingleChildScrollView(
                      child: _selectedIndex == 0
                          ? _cardTab()
                          : _accountTab(),
                    ),
                  ),
                ],
              ),
            ),
        ],         
      ),
    );
  }

  
  Widget _cardTab() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: EdgeInsets.all(5),
            width: double.infinity,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
            ),
            clipBehavior: Clip.antiAlias,
            child: Image.asset(
              "assets/images/card.png",
              fit: BoxFit.cover,
            ),
          ),

          const SizedBox(height: 10),
          const Text(
            "Картны мэдээлэл нэмэх",
            style: TextStyle(fontWeight: FontWeight.bold),
          ),

          const SizedBox(height: 12),
          _input("Карт дээрх нэр"),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(flex: 2, child: _input("Картны дугаар")),
              const SizedBox(width: 10),
              Expanded(flex: 1, child: _input("CVC")),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(flex: 2, child: _input("Дуусах хугацаа")),
              const SizedBox(width: 10),
              Expanded(flex: 1, child: _input("ZIP")),
            ],
          ),
          const SizedBox(height: 10),
        
          _input("Цэнэглэх дүн",controller: _amountController),
          const SizedBox(height: 20),
          _mainButton("ЦЭНЭГЛЭХ"),
        ],
      ),
    );
  }
  

  Widget _accountTab() {
    return Column(
      children: [
        _accountTile(
          icon: Icons.account_balance,
          title: "Bank Link",
          subtitle: "Connect your bank account",
          active: true,
        ),
        _accountTile(
          icon: Icons.qr_code,
          title: "Qpay",
          subtitle: "Pay with Qpay",
        ),
        _accountTile(
          icon: Icons.attach_money,
          title: "Microdeposits",
          subtitle: "Connect bank in 5–7 days",
        ),
        _accountTile(
          icon: Icons.paypal,
          title: "Paypal",
          subtitle: "Connect your paypal account",
        ),
        const SizedBox(height: 30),
        _mainButton("ДАРААХ"),
      ],
    );
  }


  Widget _accountTile({
    required IconData icon,
    required String title,
    required String subtitle,
    bool active = false,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: active ? const Color(0xFFE8F6F3) : Colors.grey[100],
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(icon, color: Colors.teal),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.bold)),
                Text(subtitle,
                    style: const TextStyle(color: Colors.grey)),
              ],
            ),
          ),
          if (active)
            const Icon(Icons.check_circle, color: Colors.teal),
        ],
      ),
    );
  }

  
  Widget _input(String hint, {TextEditingController? controller}) {
    return TextField(
      controller: controller,
      keyboardType: hint == "Цэнэглэх дүн" ? TextInputType.number : TextInputType.text,
      decoration: InputDecoration(
        hintText: hint,
        filled: true,
        fillColor: Colors.grey[100],
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(20),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }

  Widget _mainButton(String text) {
    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: Colors.teal,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
            side: const BorderSide(color: Colors.teal),
          ),
        ),
        onPressed: () async {
          if (text == "ЦЭНЭГЛЭХ") {
            // 1. Оруулсан дүнг тоо болгож хувиргах
            double amount = double.tryParse(_amountController.text) ?? 0.0;

            if (amount > 0) {
              // 2. Hive box-оос одоогийн балансыг унших
              var historyBox= Hive.box<TransactionItem>('history_box');

              // 4. Түүх рүү (History) орлого гэж нэмэх
              await historyBox.add(TransactionItem(
                id: DateTime.now().toString(),
                service: "Картнаас цэнэглэлт",
                amount: amount, // Орлого тул нэмэх утга
                date: DateTime.now(),
              ));

              // 5. Амжилттай болсон мэдэгдэл харуулах
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text("\$${amount} амжилттай нэмэгдлээ!")),
              );

              // 6. Түрийвч рүү буцах
              Navigator.pop(context);
            } else {
              // Дүн буруу үед алдаа харуулах
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Зөв дүн оруулна уу!")),
              );
            }
          }
        },
        child: Text(text, style: const TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _tabButton(String title, int index) {
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedIndex = index),
        child: Center(
          child: Text(
            title,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color:
                  _selectedIndex == index ? Colors.black : Colors.grey,
            ),
          ),
        ),
      ),
    );
  }

  
  Widget _bottomNav(BuildContext context, int currentIndex) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 12),
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
                  MaterialPageRoute(
                      builder: (_) => const HomePage()),
                );
              }
            },
            child: Icon(
              Icons.home,
              color: currentIndex == 0
                  ? Colors.teal
                  : Colors.grey,
              size: 30,
            ),
          ),
          const Icon(Icons.bar_chart, color: Colors.grey, size: 30),
          InkWell(
            onTap: () {
              if (currentIndex != 2) {
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(
                      builder: (_) => const WalletScreen()),
                );
              }
            },
            child: Icon(
              Icons.account_balance_wallet,
              color: currentIndex == 2
                  ? Colors.teal
                  : Colors.grey,
              size: 30,
            ),
          ),
          const Icon(Icons.person, color: Colors.grey, size: 30),
        ],
      ),
    );
  }
}
