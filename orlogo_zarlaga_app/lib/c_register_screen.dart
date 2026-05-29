import 'package:flutter/material.dart';
import 'd_login_screen.dart';
import 'package:hive_flutter/hive_flutter.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
    final TextEditingController name = TextEditingController();
    final TextEditingController email = TextEditingController();
    final TextEditingController pass1 = TextEditingController();
    final TextEditingController pass2 = TextEditingController();


    void _register() {
      if (name.text.isEmpty || email.text.isEmpty || pass1.text.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Бүх талбарыг бөглөнө үү!")),
        );
        return;
      }

      if (pass1.text != pass2.text) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Нууц үг таарахгүй байна!")),
        );
        return;
      }

      var box = Hive.box('userBox');

      box.put('email', email.text);
      box.put('password', pass1.text);
      box.put('name', name.text);

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Амжилттай бүртгэгдлээ! Нэвтрэнэ үү.")),
      );

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const LoginScreen()),
      );
    }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF2F4F6),
      body: SingleChildScrollView(
        child: Column(
          children: [
            Stack(
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
                  top: 100,
                  left: 0,
                  right: 0,
                  child: Column(
                    children: const [
                      Text(
                        "Тавтай морилно уу?",
                        style: TextStyle(
                          fontSize: 22,
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(height: 8),
                      Text(
                        "Орлого, зарлагаа хянахад тань туслана",
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.white70,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(height: 25),

            _inputField("Бүтэн нэрээ оруулна уу?", name),
            _inputField("Имэйлээ оруулна уу?", email),
            _inputField("Нууц үгээ оруулна уу?", pass1, isPass: true),
            _inputField("Нууц үгээ дахин оруулна уу?", pass2, isPass: true),
            const SizedBox(height: 20),
         
            GestureDetector(
              onTap: _register,
              child: Container(
                width: 220,
                height: 50,
                decoration: BoxDecoration(
                  color: const Color(0xFF267B6E),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: const Center(
                  child: Text(
                    "Бүртгүүлэх",
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 20),

            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text("Хэрэглэгчийн эрхтэй юу? "),
                GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => const LoginScreen(),
                      ),
                    );
                  },
                  child: const Text(
                    "Нэвтрэх",
                    style: TextStyle(
                      color: Colors.teal,
                      decoration: TextDecoration.underline,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _inputField(String hint, TextEditingController ctrl,
      {bool isPass = false}) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      child: TextField(
        controller: ctrl,
        obscureText: isPass,
        decoration: InputDecoration(
          hintText: hint,
          filled: true,
          fillColor: Colors.white,
          contentPadding:
              const EdgeInsets.symmetric(vertical: 18, horizontal: 15),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(25),
            borderSide: BorderSide.none,
          ),
        ),
      ),
    );
  }
}
