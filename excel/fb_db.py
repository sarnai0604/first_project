import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from curl_cffi import requests as cf_requests
import pyodbc

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
COOKIE_FILE = "all_accounts_cookies.json"

# MS SQL Server холболтын мэдээлэл
DB_CONFIG = {
    "server": "10.10.15.202",
    "database": "sumbee",
    "username": "user_web",
    "password": "b70i0V$>Ht?m",
    "driver": "{ODBC Driver 17 for SQL Server}"
}

# Thread-safe байх үүднээс lock ашиглана
cookie_lock = threading.Lock()


def get_db_connection():
    """SQL Server рүү холболт үүсгэх"""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    return pyodbc.connect(conn_str)


def load_all_cookies():
    """JSON файл руу хадгалсан бүх аккаунтын cookie-г уншиж бэлтгэх"""
    if not os.path.exists(COOKIE_FILE):
        print(f"❌ Анхаар: '{COOKIE_FILE}' файл олдсонгүй!")
        return []

    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        valid_cookies_list = []
        for username, info in data.items():
            if info.get("status") == "success" and info.get("cookies"):
                cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in info["cookies"]])
                valid_cookies_list.append({"username": username, "cookie_string": cookie_str})

        print(f"✓ '{COOKIE_FILE}' файлаас нийт {len(valid_cookies_list)} идэвхтэй cookie ачаалагдлаа.")
        return valid_cookies_list
    except Exception as e:
        print(f"❌ Cookie файл унших явцад алдаа гарлаа: {e}")
        return []


ACTIVE_COOKIES = load_all_cookies()


def parse_count(text):
    if not text:
        return 0

    text = str(text).strip().upper().replace(",", "")

    try:
        match = re.search(r"(\d+(?:\.\d+)?)\s*([KMB]?)", text)

        if not match:
            return 0

        number = float(match.group(1))
        suffix = match.group(2)

        multiplier = {
            "": 1,
            "K": 1_000,
            "M": 1_000_000,
            "B": 1_000_000_000
        }

        return int(number * multiplier[suffix])

    except Exception:
        return 0


def _extract_locations(html):
    lives_in = ""
    from_place = ""

    m_lives = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if not m_lives:
        m_lives = re.search(r'"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if m_lives:
        lives_in = m_lives.group(1).strip()

    m_from = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"From\s+([^"]+)"', html)
    if not m_from:
        m_from = re.search(r'"text"\s*:\s*"From\s+([^"]+)"', html)
    if m_from:
        from_place = m_from.group(1).strip()

    if len(lives_in) > 500:
        lives_in = ""
    if len(from_place) > 500:
        from_place = ""

    return lives_in, from_place


def clean_unicode_text(text):
    if not text:
        return ""
    try:
        # Хэрэв \u00f6 гэх мэт escape тэмдэгт агуулсан байвал хөрвүүлэх
        if "\\u" in text:
            text = text.encode().decode("unicode-escape")
    except Exception:
        pass

    try:
        # Эможи болон MS SQL-ийн дэмждэггүй суррогат тэмдэгтүүдийг (surrogates) хасах
        text = text.encode('utf-8', 'ignore').decode('utf-8')
    except Exception:
        pass
    
    return text.strip()


def _extract_status(html):
    status_patterns = [
        (r'>\s*Married\s*<', "married"),
        (r'>\s*Engaged\s*<', "engaged"),
        (r'>\s*In a relationship\s*<', "in a relationship"),
        (r'>\s*Separated\s*<', "separated"),
        (r'>\s*Divorced\s*<', "divorced"),
        (r'>\s*Single\s*<', "single"),
        (r'>\s*Гэрлэсэн\s*<', "married"),
        (r'>\s*Сүй тавьсан\s*<', "engaged"),
        (r'>\s*Үерхдэг\s*<', "in a relationship"),
        (r'>\s*Тусдаа амьдардаг\s*<', "separated"),
        (r'>\s*Салсан\s*<', "divorced"),
        (r'>\s*Ганц бие\s*<', "single"),
    ]
    for pattern, value in status_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return value
    return ""


def _extract_category(html):
    from html import unescape
    pattern = re.compile(
        r'<div[^>]*role=["\']button["\'][^>]*>'
        r"\s*([^<]+?)"
        r'\s*<div[^>]*role=["\']none["\']',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(html):
        value = unescape(m.group(1)).strip()
        if value:
            return value
    return ""


def do_lookup(q):
    print(f"🔄 [Шалгаж байна] ID: {q}...")
    time.sleep(0.5)
    
    empty_res = {
        "username": "", "id": q, "friends": 0, "followers": 0, "following": 0,
        "gender": "", "is_closed": 0, "lives_in": "", "from_place": "", "status": "", "category": ""
    }

    if not str(q).isdigit():
        return empty_res

    global ACTIVE_COOKIES
    session = cf_requests.Session(impersonate="chrome120")

    attempts = 0
    while attempts < len(ACTIVE_COOKIES):
        with cookie_lock:
            if not ACTIVE_COOKIES:
                break
            current_cookie = ACTIVE_COOKIES.pop(0)

        headers = {"User-Agent": USER_AGENT, "Cookie": current_cookie["cookie_string"]}

        try:
            resp = session.get(
                f"https://www.facebook.com/{q}",
                headers=headers,
                timeout=10,
                allow_redirects=True,
            )

            if "login" in resp.url or "checkpoint" in resp.url:
                attempts += 1
                continue

            with cookie_lock:
                ACTIVE_COOKIES.append(current_cookie)

            final_url = resp.url.rstrip("/").split("?")[0].split("#")[0]
            slug = final_url.split("facebook.com/")[-1].strip("/")
            if not (slug and slug != str(q) and not slug.isdigit() and slug.lower() != "profile.php" and re.match(r"^[\w.]+$", slug)):
                slug = ""

            html_content = resp.text

            # Friends
            m_friends = re.search(r"([\d.,KkMmBb]+)\s*<\/strong>\s*(?:friends|найз)", html_content, re.IGNORECASE)
            if not m_friends:
                m_friends = re.search(r"([\d.,KkMmBb]+)\s*(?:friends|найз)", html_content, re.IGNORECASE)
            friends = parse_count(m_friends.group(1)) if m_friends else 0

            # Followers
            m_followers = re.search(r"([\d.,KkMmBb]+)\s*<\/strong>\s*(?:followers|дагагч)", html_content, re.IGNORECASE)
            if not m_followers:
                m_followers = re.search(r"([\d.,KkMmBb]+)\s*(?:followers|дагагч)}", html_content, re.IGNORECASE)
            followers = parse_count(m_followers.group(1)) if m_followers else 0

            # Following
            m_following = re.search(r"([\d.,KkMmBb]+)\s*<\/strong>\s*(?:following|дагаж)", html_content, re.IGNORECASE)
            if not m_following:
                m_following = re.search(r"([\d.,KkMmBb]+)\s*(?:following|дагаж)", html_content, re.IGNORECASE)
            following = parse_count(m_following.group(1)) if m_following else 0

            # Gender
            gender = ""
            m_gender = re.search(r'"\s*,\s*"gender"\s*:\s*"?(\w+)"?', html_content)
            if m_gender:
                raw = m_gender.group(1).lower()
                if raw in ["male", "female", "neuter", "unknown"]:
                    gender = raw

            # Locked / Open шалгах хэсэг
            if (
                '"LockedProfileTryItBanner"' in html_content
                or "locked her profile" in html_content
                or "locked his profile" in html_content
                or "locked their profile" in html_content
            ):
                is_closed = 1
            else:
                is_closed = 0

            lives_in, from_place = _extract_locations(html_content)
            lives_in = clean_unicode_text(lives_in)
            from_place = clean_unicode_text(from_place)

            print(f"✅ [Амжилттай] ID: {q} (Username: {slug}) мэдээлэл олдлоо.")
            
            session.close()
            return {
                "username": slug,
                "id": str(q),
                "friends": friends,
                "followers": followers,
                "following": following,
                "gender": gender,
                "is_closed": is_closed,
                "lives_in": lives_in,
                "from_place": from_place,
                "status": _extract_status(html_content),
                "category": _extract_category(html_content),
            }

        except Exception as e:
            with cookie_lock:
                ACTIVE_COOKIES.append(current_cookie)
            attempts += 1

    session.close()
    print(f"❌ [Амжилтгүй] ID: {q} мэдээлэл татаж чадсангүй.")
    return empty_res


def update_database_batch(results, batch_size=100):
    """Өгөгдлийг багцлаад (Batch) SQL Server руу UPDATE хийх"""
    if not results:
        return
    
    query = """
        UPDATE [sumbee].[dbo].[Facebook.Acc]
        SET 
            UserName = ?, 
            FriendsCount = ?, 
            FollowersCount = ?, 
            FollowingCount = ?, 
            isLockedProfile = ?, 
            Gender = ?, 
            CurrentCityName = ?, 
            HomeTownName = ?, 
            Status = ?, 
            Category = ?,
            Caption = '2026.08.31, ' + LEFT(CONVERT(VARCHAR(19), GETDATE(), 120), 16)
        WHERE FbID = ? 
    """

    total_records = len(results)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for i in range(0, total_records, batch_size):
            batch = results[i:i + batch_size]
            params = []
            for r in batch:
                params.append((
                    r["username"], r["friends"], r["followers"], r["following"],
                    r["is_closed"], r["gender"], r["lives_in"], r["from_place"],
                    r["status"], r["category"], r["id"]
                ))
            
            cursor.executemany(query, params)
            conn.commit()
            print(f"💾 [DB] {i + len(batch)}/{total_records} бичлэг шинэчлэгдлээ...")
        cursor.close()
        conn.close()
        print(f"💾 [DB] Нийт {len(results)} бичлэг датабааз руу шалгагдаж хадгалагдлаа.")
    except Exception as e:
        print(f"❌ DB Update Error: {e}")


def run_sync_process(batch_size=100):
    sql_query_clean = """
        SELECT TOP (5000)
            FbID, UserName
        FROM [sumbee].[dbo].[Facebook.Acc]
        WHERE UserName is null
    """
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query_clean)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        fb_ids = [str(row.FbID) for row in rows if row.FbID]
        if not fb_ids:
            print("⚠️ Шалгах идэвхтэй ID олдсонгүй.")
            return
        
        total_ids = len(fb_ids)
        print(f"🚀 Нийт {total_ids} идэвхтэй ID олдлоо. {batch_size}-гаар нь багцлан шалгаж эхэлж байна...\n" + "-"*40)
        
        # ID-уудыг batch_size (100)-аар нь хувааж давтах
        for i in range(0, total_ids, batch_size):
            chunk_ids = fb_ids[i:i + batch_size]
            print(f"\n📦 Багц: {i + 1} - {min(i + batch_size, total_ids)} / {total_ids} шалгаж байна...")
            
            # Тухайн багцыг thread-үүдээр зэрэг шалгах
            workers = min(10, len(chunk_ids))
            with ThreadPoolExecutor(max_workers=workers) as ex:
                chunk_results = list(ex.map(do_lookup, chunk_ids))
                
            # Шалгаж дуусаад шууд датабааз руу хадгалах
            update_database_batch(chunk_results, batch_size=batch_size)
            
        print("\n✨ Бүх багц амжилттай шалгагдаж дууслаа!")

    except Exception as e:
        print(f"❌ Process Error: {e}")


if __name__ == "__main__":
    run_sync_process()