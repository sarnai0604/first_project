import asyncio
import json
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
# COOKIE PARSER FOR PLAYWRIGHT
# ============================================================
def parse_cookies_from_db(cookie_raw, domain=".facebook.com"):
    """
    Баазаас ирсэн cookie (JSON формат эсвэл string байж болно)-г
    Playwright ойлгох форматад хөрвүүлнэ.
    """
    if not cookie_raw:
        return []
    
    pw_cookies = []
    try:
        if cookie_raw.strip().startswith("[") or cookie_raw.strip().startswith("{"):
            cookie_list = json.loads(cookie_raw)
            if isinstance(cookie_list, dict):
                cookie_list = [cookie_list]
            for c in cookie_list:
                name = c.get("name")
                value = c.get("value")
                if name and value:
                    pw_cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/"
                    })
        else:
            parts = cookie_raw.strip().split(";")
            for part in parts:
                if "=" in part:
                    name, value = part.strip().split("=", 1)
                    pw_cookies.append({
                        "name": name, 
                        "value": value, 
                        "domain": domain, 
                        "path": "/"
                    })
    except Exception as e:
        print(f"❌ Cookie задлахад алдаа гарлаа: {e}")
        
    return pw_cookies

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
    except Exception:
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
    
    is_not_found = 1 if sql_date is None else 0
    return (sql_date, is_not_found, str(user_id))

async def process_database_profiles():
    # 1. Баазаас Type = 'Accounts' гэсэн нөхцөлтэй хэрэглэгчдийг татаж авах
    cookie_sets = []
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        cookie_query = """
            SELECT ID, User_Name, Cookies, isExpiredCookies, Group_Number
            FROM [sumbee].[dbo].[Facebook.Users]
            WHERE Type = 'Accounts' AND Cookies IS NOT NULL AND Cookies != ''
        """
        cursor.execute(cookie_query)
        cookie_rows = cursor.fetchall()
        
        for c_row in cookie_rows:
            db_id, username, raw_cookie, is_expired, group_no = c_row
            # Хэрэв cookie нь хүчинтэй (isExpiredCookies != 1) байвал цуглуулна
            if is_expired != 1:
                parsed = parse_cookies_from_db(raw_cookie)
                if parsed:
                    cookie_sets.append({"id": db_id, "username": username, "cookies": parsed})
        
        conn.close()
        
        # Яг 5 ширхгийг л шүүж авна
        cookie_sets = cookie_sets[:5]
        print(f"✓ Өгөгдлийн сангаас Type='Accounts' бүхий идэвхтэй {len(cookie_sets)} ширхэг cookie амжилттай бэлтгэгдлээ.")
    except Exception as e:
        print(f"❌ Cookie татахад алдаа гарлаа: {e}")
        return

    if not cookie_sets:
        print("Идэвхтэй cookie олдсонгүй, зогсож байна.")
        return

    # 2. Шалгах шаардлагатай Facebook ID-уудаа татаж авах
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        target_query = """
            SELECT TOP (100)
                Acc.FbID,
                Acc.UserName,
                Acc.RegistrationDate, COUNT(*)
            FROM [sumbee].[dbo].[Facebook.Posts] AS Pss
            INNER JOIN [sumbee].[dbo].[Facebook.Acc] AS Acc
                ON Pss.PageID = Acc.ID
            WHERE Pss.CreatedDate >= DATEADD(DAY, -1, GETDATE()) 
              AND Acc.FbID IS NOT NULL 
              AND Acc.UserName <> 'Anonymous participant' 
              AND Acc.RegistrationDate IS NULL 
            GROUP BY 
                Acc.FbID,
                Acc.UserName,
                Acc.RegistrationDate
            ORDER BY COUNT(*) DESC;
        """
        cursor.execute(target_query)
        rows = cursor.fetchall()
        conn.close()
        print(f"SQL Server-ээс нийт {len(rows)} шалгах ID татаж авлаа.")
    except Exception as e:
        print(f"Өгөгдлийн сантай холбогдоход алдаа гарлаа: {e}")
        return

    if not rows:
        print("Шалгах ID олдсонгүй.")
        return

    # 3. Playwright ашиглаж 5 браузер цонхыг зэрэг нээх
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        worker_pages = []
        for c_item in cookie_sets:
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            await ctx.add_cookies(c_item["cookies"])
            pg = await ctx.new_page()
            worker_pages.append(pg)

        num_workers = len(worker_pages)
        print(f"🛠️ Нийт {num_workers} worker хуудас амжилттай бэлэн боллоо.")

        batch_data = []
        batch_size = 30
        total_rows = len(rows)

        i = 0
        while i < total_rows:
            chunk = rows[i:i + num_workers]
            tasks = []
            
            for offset, row in enumerate(chunk):
                user_id = row[0]
                current_index = i + offset + 1
                
                if not user_id or not str(user_id).strip():
                    continue
                
                page_to_use = worker_pages[offset % num_workers]
                tasks.append(process_single_profile(page_to_use, user_id, current_index, total_rows))

            if tasks:
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
                        
                        update_query = """
                            UPDATE [dbo].[Facebook.Acc]
                            SET RegistrationDate = ?, isNotFound = ? 
                            WHERE FbID = ?
                        """
                        db_cursor.executemany(update_query, batch_data)
                        db_conn.commit()
                        db_conn.close()
                        
                        print("---> Багц хадгалалт амжилттай боллоо.")
                        batch_data.clear()
                    except Exception as db_err:
                        print(f"Бааз руу бичихэд алдаа гарлаа: {db_err}")

            i += len(chunk)
            await asyncio.sleep(2)

        await browser.close()

    print("\nБүх профайлын мэдээллийг шалгаж дууслаа.")

if __name__ == "__main__":
    asyncio.run(process_database_profiles())