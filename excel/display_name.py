import asyncio
import re
from playwright.async_api import async_playwright

# Та өөрийн ажилладаг күүкигээ энд байрлуулна
COOKIE_STRING = """
    datr=0f4TaniQolJ5C4YoG81CwSqZ;
    sb=0f4Tag_szj9t082e8Bc6butW;
    c_user=100021418158790;
    xs=11%3AQxOKLVnuyO3D6A%3A2%3A1787194304%3A-1%3A-1%3A%3AAcyiztEM_eGN8KNaI_q6Z9sxLV5avvnLwj8OgdOomQ;
    fr=1UKtHbKEv0MIH61kG.AWfJJpcuST_BlPO_PrUiGw4fXUICXNdN7jV-uOgo7QJ7plVWtzc.BqhmvG..AAA.0.0.BqhmvG.AWfIeTsQ1mcKegYbCfy_NPIikN0;
"""


def parse_cookies(cookie_string, domain=".facebook.com"):
    cookies = []
    parts = cookie_string.strip().split(";")
    for part in parts:
        if "=" in part:
            name, value = part.strip().split("=", 1)
            cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return cookies


async def click_profile_name(page):
    try:
        name_selector = 'span[dir="auto"] > div[role="button"][tabindex="0"].x1i10hfl.x1qjc9v5.xjbqb8w'
        name_elem = page.locator(name_selector).first
        
        if await name_elem.count() > 0:
            await name_elem.click()
            print("Профайлын нэр дээр амжилттай click хийлээ.")
            await page.wait_for_timeout(3000)
            return True
        else:
            print("Профайлын нэр олдсонгүй.")
            return False
            
    except Exception as e:
        print(f"Click хийхэд алдаа гарлаа: {e}")
        return False

    
async def get_facebook_joined_date(user_id):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context()

        # Күүки оруулах
        formatted_cookies = parse_cookies(COOKIE_STRING)
        await context.add_cookies(formatted_cookies)

        page = await context.new_page()
        profile_url = f"https://www.facebook.com/{user_id}"
        print(f"Хуудас руу орж байна: {profile_url}")
        
        joined_date = "Олдсонгүй"
        
        try:
            await page.goto(profile_url, timeout=60000)
            await page.wait_for_timeout(4000)

            await click_profile_name(page)

            # Гарч ирсэн popup цонхны текрээс мэдээллийг авах
            popup_text = await page.locator("body").inner_text()
            
            # "Joined Facebook:" гэсэн үгний араас гарч ирэх зай болон шинэ мөрөөр тусгаарлагдсан текстийг шүүж авах RegEx
            # Жишээ нь: "Joined Facebook: August 14, 2017" эсвэл шинэ мөр дээр гарсан байсан ч олно.
            joined_match = re.search(
                r'Joined\s+Facebook\s*[:\-]?\s*([^\n\r]+)', 
                popup_text, 
                re.IGNORECASE
            )
            
            if joined_match:
                # Group(1) нь "Joined Facebook:" гэсний араас ирэх утгыг буцаана (Жнь: August 14, 2017)
                joined_date = joined_match.group(1).strip()
            
            await page.wait_for_timeout(5000)

        except Exception as e:
            print(f"Алдаа гарлаа: {e}")

        await browser.close()
        return joined_date

# Туршиж үзэх хэсэг
if __name__ == "__main__":
    target_user_id = "100021418158790"
    result = asyncio.run(get_facebook_joined_date(target_user_id))
    print(f"\n--- Үр дүн ---")
    print(f"Joined Facebook: {result}")