import 'package:flutter/material.dart';
import 'package:orlogo_zarlaga_app/e_home_page.dart';
import 'c_register_screen.dart';
import 'package:hive_flutter/hive_flutter.dart';


class LoginScreen extends StatelessWidget{
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context){
    final TextEditingController email = TextEditingController();
    final TextEditingController pass = TextEditingController();

    void login() {
      final box = Hive.box('userbox');

      String? savedEmail = box.get('email');
      String? savedPass = box.get('password');

      if (savedEmail == null || savedPass == null) {
          ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Хэрэглэгч олдсонгүй! Бүртгүүлнэ үү.")),
        );
        return;
      }
      if (email.text == savedEmail && pass.text == savedPass) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => const HomePage()),
        );
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Амжилттай нэвтэрлээ!")),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Имэйл эсвэл нууц үг буруу байна!")),
        );
      }
    }

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
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(height: 30),
            _inputField("Имэйлээ оруулна уу?", email),
            _inputField("Нууц үгээ оруулна уу?", pass, isPass: true),
            
            const SizedBox(height: 25),
            GestureDetector(
              onTap: login,
              child: Container(
                width: 220,
                height: 50,
                decoration: BoxDecoration(
                  color: const Color(0xFF267B6E),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: const Center(
                  child: Text(
                    "Нэвтрэх",
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
                Text("Хэрэглэгчийн эрхтэй юу?  "),
                GestureDetector(
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => const RegisterScreen(),
                      ),
                    );
                  },
                  child: const Text(
                    "Бүртгүүлэх",
                    style: TextStyle(
                      color: Colors.teal,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ],
            ),
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

