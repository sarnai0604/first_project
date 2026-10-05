import asyncio
import re
from datetime import datetime
import pyodbc
from playwright.async_api import async_playwright

# ============================================================
# SQL SERVER CONNECTION SETTINGS
# ============================================================
DB_SERVER = "10.10.15.202" 
DB_NAME = "sumbee"
DB_USER = "user_web"
DB_PASSWORD = "b70i0V$>Ht?m"

CONNECTION_STRING = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASSWORD}"

# ============================================================
# COOKIE SETTINGS (3 ӨӨР COOKIE)
# ============================================================
COOKIE_STRING_1 = """
    datr=QJiCahJOUkel9V_Je2hoK8rE;
    sb=QJiCamJa2GunQU0RHYBUEwZy;
    c_user=100090316622127;
    xs=15%3AeOl9W3ffkgSdCA%3A2%3A1787714621%3A-1%3A-1%3A%3AAcyEJdiU15dZtPumH7UY06IRyw07JOU9aE1k1Q2XWsz0;
    fr=1ishckVFTEEIrsMwl.AWfR1u0ALfbqSkGfdRZ4u_AdbGUMhDckJ5H4BaHj5fpUAkAdsaE.BqvHIX..AAA.0.0.BqvHIX.AWduh9ysS3i5pjrmjZsfuEVymzk;
"""

COOKIE_STRING_2 = """
    datr=cd2aaJ6mcbboFUomocO2pmX4;
    sb=cd2aaMWO5Bqe1MxEb-EZCjJp;
    c_user=100021418158790;
    xs=26%3ANUSdrCMCWcEheg%3A2%3A1789966953%3A-1%3A-1%3A%3AAcwvYzHHvW9MirM2YH1LfcZ9skJ4-3k1cVlGYekeGgI;
    fr=1C9c9gBPWqaoyCZIU.AWeAYvQbz3hZ6FKCcS1BJb2pgUMYfVm12sWjdUBYQL1UTw5PsdI.BqvHIp..AAA.0.0.BqvHIp.AWcSTrB0WlxSXm7CuZz8wor7VvE;
""" 

COOKIE_STRING_3 = """
    datr=0f4TaniQolJ5C4YoG81CwSqZ;
    sb=0f4Tag_szj9t082e8Bc6butW;
    c_user=61593179188492;
    xs=43%3Am2owunSNTsSdiA%3A2%3A1790562116%3A-1%3A-1%3A%3AAcwi7PlkjxSGj8TQr7fnigx1m8PsEOsp7BYqnxFK-UU;
    fr=1G2xLr3QlYb1PuPit.AWfQ-FYQYK2cp5RnA4wpyM11l-oA_XGyJ7xkx7lcP1Vl96Z5wqE.BqvHJu..AAA.0.0.BqvHJu.AWfcj0OUTETBFTQ7VP90svnQ858;
""" 

def parse_cookies(cookie_string, domain=".facebook.com"):
    cookies = []
    parts = cookie_string.strip().split(";")
    for part in parts:
        if "=" in part:
            name, value = part.strip().split("=", 1)
            cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return cookies

def convert_to_sql_date(date_string):
    if not date_string or date_string == "Олдсонгүй":
        return None
    
    clean_date_str = date_string.strip()
    
    if re.match(r'^\d{4}$', clean_date_str):
        parsed_date = datetime.strptime(f"{clean_date_str}-01-01", "%Y-%m-%d")
        return parsed_date.strftime("%Y-%m-%d 00:00:00.000")
    
    formats_to_try = [
        "%B %d, %Y",  # June 14, 2006
        "%b %d, %Y",  # Jun 14, 2006
        "%Y-%m-%d",   # 2006-06-14
    ]
    
    parsed_date = None
    for fmt in formats_to_try:
        try:
            parsed_date = datetime.strptime(clean_date_str, fmt)
            break
        except ValueError:
            continue
            
    if not parsed_date:
        try:
            match = re.search(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', clean_date_str)
            if match:
                month_str, day_str, year_str = match.groups()
                combined = f"{month_str} {day_str}, {year_str}"
                parsed_date = datetime.strptime(combined, "%B %d, %Y")
            else:
                match_my = re.search(r'([A-Za-z]+)\s+(\d{4})', clean_date_str)
                if match_my:
                    month_str, year_str = match_my.groups()
                    parsed_date = datetime.strptime(f"{month_str} 1, {year_str}", "%B %d, %Y")
        except Exception:
            pass
            
    if parsed_date:
        return parsed_date.strftime("%Y-%m-%d 00:00:00.000")
        
    return None

async def click_profile_name(page):
    try:
        name_selector = 'span[dir="auto"] > div[role="button"][tabindex="0"].x1i10hfl.x1qjc9v5.xjbqb8w'
        name_elem = page.locator(name_selector).first
        
        if await name_elem.count() > 0:
            await name_elem.click()
            await page.wait_for_timeout(3000)
            return True
        else:
            return False
            
    except Exception as e:
        return False

async def get_facebook_joined_date(page, user_id):
    profile_url = f"https://www.facebook.com/{user_id}"
    joined_date = "Олдсонгүй"
    
    try:
        await page.goto(profile_url, timeout=60000)
        await page.wait_for_timeout(4000)

        await click_profile_name(page)

        popup_text = await page.locator("body").inner_text()
        
        match = re.search(
            r'(?:Joined\s+Facebook|Created:)\s*[:\-]?\s*([^\n\r]+)', 
            popup_text, 
            re.IGNORECASE
        )
        
        if match:
            joined_date = match.group(1).strip()
        
        await page.wait_for_timeout(2000)

    except Exception as e:
        print(f"Алдаа гарлаа ({user_id}): {e}")

    return joined_date

async def process_single_profile(page, user_id, index, total_rows):
    print(f"\n--- [{index}/{total_rows}] Шалгаж буй ID: {user_id} ---")
    raw_date = await get_facebook_joined_date(page, user_id)
    print(f"Facebook-ээс олдсон текст: {raw_date}")

    sql_date = convert_to_sql_date(raw_date)
    print(f"Хөрвүүлсэн огноо: {sql_date}")
    
    # Огноо олдвол isNotFound = 0, олдоогүй бол isNotFound = 1 болгох
    if sql_date is None:
        is_not_found = 1
    else:
        is_not_found = 0
        
    return (sql_date, is_not_found, str(user_id))

async def process_database_profiles():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        query = """
            SELECT 
                Acc.FbID,
                Acc.UserName,
                Acc.RegistrationDate,COUNT(*)
            FROM [sumbee].[dbo].[Facebook.Posts] AS Pss
            INNER JOIN [sumbee].[dbo].[Facebook.Acc] AS Acc
                ON Pss.PageID = Acc.ID
            WHERE Pss.CreatedDate >= DATEADD(DAY, -1, GETDATE()) and Acc.FbID is not null AND Acc.UserName<>'Anonymous participant' 
            AND Acc.RegistrationDate is null 
            GROUP BY 
                Acc.FbID,
                Acc.UserName,
                Acc.RegistrationDate
            Order by COUNT(*) desc;
        """

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        print(f"SQL Server-ээс нийт {len(rows)} ID татаж авлаа.")
    except Exception as e:
        print(f"Өгөгдлийн сантай холбогдоход алдаа гарлаа: {e}")
        return

    if not rows:
        print("Шалгах ID олдсонгүй.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        
        context2 = await browser.new_context()
        context3 = await browser.new_context()
        context4 = await browser.new_context()

        await context2.add_cookies(parse_cookies(COOKIE_STRING_1))
        await context3.add_cookies(parse_cookies(COOKIE_STRING_2))
        await context4.add_cookies(parse_cookies(COOKIE_STRING_3))

        page2 = await context2.new_page()
        page3 = await context3.new_page()
        page4 = await context4.new_page()

        batch_data = []
        batch_size = 30
        total_rows = len(rows)

        i = 0
        while i < total_rows:
            chunk = rows[i:i+3]  # 3 хуудсаар зэрэг ажиллах тул 3-аар тасална
            tasks = []
            
            for offset, row in enumerate(chunk):
                user_id = row[0]
                current_index = i + offset + 1
                
                if not user_id or not str(user_id).strip():
                    continue
                
                if offset == 0:
                    tasks.append(process_single_profile(page2, user_id, current_index, total_rows))
                elif offset == 1:
                    tasks.append(process_single_profile(page3, user_id, current_index, total_rows))
                else:
                    tasks.append(process_single_profile(page4, user_id, current_index, total_rows))

            results = await asyncio.gather(*tasks)

            for res in results:
                if res:
                    batch_data.append(res)

            if len(batch_data) >= batch_size or (i + len(chunk)) >= total_rows:
                if batch_data:
                    try:
                        print(f"\n---> {len(batch_data)} ширхэг өгөгдлийг базад хадгалж байна...")
                        db_conn = pyodbc.connect(CONNECTION_STRING)
                        db_cursor = db_conn.cursor()
                        
                        # Олдсон бол шинэ огноо, олдоогүй бол RegistrationDate хуучин утгаар нь (NULL хэвээр) үлдээнэ
                        update_query = """
                            UPDATE [dbo].[Facebook.Acc]
                            SET RegistrationDate = COALESCE(?, RegistrationDate), isNotFound = ? 
                            WHERE FbID = ?
                        """
                        db_cursor.executemany(update_query, batch_data)
                        db_conn.commit()
                        db_conn.close()
                        
                        print("---> Багц хадгалалт амжилттай боллоо.")
                        batch_data.clear()
                    except Exception as db_err:
                        print(f"Бааз руу бичихэд алдаа гарлаа: {db_err}")

            i += 3  # 3-аар нэмэгдүүлнэ
            await asyncio.sleep(3)

        await browser.close()

    print("\nБүх профайлын мэдээллийг шалгаж дууслаа.")

if __name__ == "__main__":
    asyncio.run(process_database_profiles())