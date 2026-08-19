import asyncio
import json
import re
import pyodbc
from playwright.async_api import async_playwright

COOKIE_STRING = """
    datr=0f4TaniQolJ5C4YoG81CwSqZ;
    sb=0f4Tag_szj9t082e8Bc6butW;
    c_user=100021418158790;
    xs=8%3AwLNtoHNhRy9koA%3A2%3A1787020295%3A-1%3A-1%3A%3AAcypOVMrf1M7y489HxpzwRWRSEIjWLq4jhiJpAQd8sg;
    fr=1RkXXYMkcdsrbAF8d.AWe4V8BlEYaUmTP2MXpu29DxhN6H3268iGPOqipvrXIAyZ8oOHY.BqhRj3..AAA.0.0.BqhRj3.AWds7aShSaZLyZG1UjoEOVXKtH8;
"""

# SQL SERVER CONNECTION SETTINGS
DB_SERVER = "10.10.15.202" 
DB_NAME = "sumbee"
DB_USER = "user_web"
DB_PASSWORD = "b70i0V$>Ht?m"

CONNECTION_STRING = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASSWORD}"

def get_profile_ids_from_db():
    """SQL Server баазаас profile_id-уудыг уншиж авах"""
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        cursor.execute("SELECT fbID FROM [dbo].[Facebook.Acc]")
        rows = cursor.fetchall()
        conn.close()
        
        return [str(row[0]) for row in rows]
    except Exception as e:
        print(f"⚠️ SQL Server өгөгдлийн сан руу холбогдох эсвэл өгөгдөл унших үед алдаа гарлаа: {e}")
        return []

def save_data_to_db(profile_id, data_dict):
    """Олдсон мэдээллээс stats-ийг салгаж тусгай багануудад, мөн JSON-ийг хамт хадгалах"""
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # 1. Бүх цуглуулсан мэдээллийг JSON string болгох
        json_data = json.dumps(data_dict, ensure_ascii=False)
        
        # 2. Stats (тоон мэдээллүүд)-ийг тусад нь салгаж авах (Олдоогүй бол None буюу базад NULL болж орно)
        stats = data_dict.get("stats", {})
        friends_count = stats.get("friends")
        followers_count = stats.get("followers")
        following_count = stats.get("following")
        likes_count = stats.get("likes")
        
        # 3. SQL Server бааз руугаа багана тус бүрээр UPDATE хийх
        sql_query = """
            UPDATE profiles 
            SET scraped_data = ?,
                FriendsCount = ?,
                FollowersCount = ?,
                FollowingCount = ?,
                LikesCount = ?
            WHERE profile_id = ?
        """
        
        cursor.execute(sql_query, (
            json_data, 
            friends_count, 
            followers_count, 
            following_count, 
            likes_count, 
            profile_id
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Базад хадгалах үед алдаа гарлаа (ID: {profile_id}): {e}")

def parse_cookies(cookie_string, domain=".facebook.com"):
    cookies = []
    parts = cookie_string.strip().split(";")
    for part in parts:
        if "=" in part:
            name, value = part.strip().split("=", 1)
            cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return cookies

async def scrape_facebook_profile():
    profile_ids = get_profile_ids_from_db()
    
    if not profile_ids:
        print("⚠️ Өгөгдлийн сангаас ямар нэгэн ID олдсонгүй эсвэл холбогдож чадсангүй.")
        return

    print(f"📌 SQL Server базаас нийт {len(profile_ids)} ширхэг ID олдлоо. Scraping эхэлж байна...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        formatted_cookies = parse_cookies(COOKIE_STRING)
        await context.add_cookies(formatted_cookies)
        page = await context.new_page()

        for user_id in profile_ids:
            print(f"\n--------------------------------------------------")
            print(f"🔄 Профайл боловсруулж байна: ID = {user_id}")
            print(f"--------------------------------------------------")
            
            scraped_data = {}
            
            url_mapping = {
                "intro": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_intro",
                "category": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_category",
                "personal_details": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_personal_details",
                "work": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_work",
                "education": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_education",
                "hobbies": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_activites",
                "interests": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_interests",
                "travel": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_travel",
                "links": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_links",
                "contact_info": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_contact_info",
                "names": f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_names",
                "aboutyou": f"https://www.facebook.com/profile.php?id={user_id}&sk=about_details"
            }

            main_about_url = f"https://www.facebook.com/profile.php?id={user_id}&sk=about"
            
            try:
                await page.goto(main_about_url, timeout=60000)
                await page.wait_for_timeout(4000)

                full_page_text = await page.locator("body").inner_text()
                
                friends_match = re.search(r'([\d,\.KMB]+)\s+Friends', full_page_text, re.IGNORECASE)
                followers_match = re.search(r'([\d,\.KMB]+)\s+Followers', full_page_text, re.IGNORECASE)
                following_match = re.search(r'([\d,\.KMB]+)\s+Following', full_page_text, re.IGNORECASE)
                likes_match = re.search(r'([\d,\.KMB]+)\s+Likes', full_page_text, re.IGNORECASE)

                stats = {}
                if friends_match:
                    stats["friends"] = friends_match.group(1).replace(",", "")
                if followers_match:
                    stats["followers"] = followers_match.group(1).replace(",", "")
                if following_match:
                    stats["following"] = following_match.group(1).replace(",", "")
                if likes_match:
                    stats["likes"] = likes_match.group(1).replace(",", "")

                if stats:
                    scraped_data["stats"] = stats

                active_keys = set()
                sidebar_container = page.locator('div.x1yztbdb').first
                
                if await sidebar_container.count() > 0:
                    menu_items = sidebar_container.locator('a, span, div[role="link"]')
                    count = await menu_items.count()
                    found_texts = []
                    
                    for i in range(count):
                        txt = await menu_items.nth(i).inner_text()
                        if txt:
                            found_texts.append(txt.strip().lower())

                    mapping_keywords = {
                        "intro": "intro",
                        "category": "category",
                        "personal details": "personal_details",
                        "work": "work",
                        "education": "education",
                        "hobbies": "hobbies",
                        "interests": "interests",
                        "travel": "travel",
                        "links": "links",
                        "contact info": "contact_info",
                        "names": "names",
                        "details about you": "aboutyou"
                    }

                    for key_phrase, url_key in mapping_keywords.items():
                        if any(key_phrase in ft for ft in found_texts):
                            active_keys.add(url_key)

                if not active_keys:
                    active_keys = {"intro", "category", "contact_info"}

                print(f"Шалгаж үзэх идэвхтэй секцүүд: {active_keys}")

                for key in active_keys:
                    if key not in url_mapping:
                        continue
                    url = url_mapping[key]
                    try:
                        await page.goto(url, timeout=60000)
                        await page.wait_for_timeout(3000)

                        data = await extract_data_by_section(page, key)
                        if data:
                            scraped_data[key] = data
                    except Exception as e:
                        print(f"⚠️ Алдаа гарлаа [{key}]: {e}")

                save_data_to_db(user_id, scraped_data)
                print(f"✅ ID: {user_id} - Мэдээлэл амжилттай SQL Server базад хадгалагдлаа.")

            except Exception as e:
                print(f"❌ Профайл руу ороход алдаа гарлаа (ID: {user_id}): {e}")

        await browser.close()
        print("\n🎉 Бүх профайлын мэдээллийг амжилттай татаж SQL Server базад хадчихаллаа!")


async def extract_data_by_section(page, section_type):
    extracted = {}

    if section_type == "intro":
        try:
            bio_heading = page.locator('h2').filter(has_text="Bio").first
            if await bio_heading.count() > 0:
                section = bio_heading.locator("xpath=ancestor::section[1]")
                bio_locator = section.locator('div[dir="auto"][style*="text-align"]').first
                if await bio_locator.count() > 0:
                    bio = (await bio_locator.inner_text()).strip()
                    extracted["bio"] = bio if bio else None
        except Exception as e:
            print(f"Bio авахад алдаа: {e}")
    
    try:
        main = page.locator("div[role='main']")
        headings = main.locator("h2")
        result = []

        for i in range(await headings.count()):
            heading = headings.nth(i)
            title = (await heading.inner_text()).strip()
            if not title:
                continue

            section = heading.locator("xpath=ancestor::section[1]")
            if await section.count() == 0:
                continue

            texts = await section.locator('[dir="auto"]').all_inner_texts()
            clean_texts = []

            for text in texts:
                text = text.strip()
                if not text:
                    continue

                unwanted = [
                    "Shared with Public", "Shared with Friends", 
                    "Edit", "Edit details", "See more", "See less"
                ]

                if text in unwanted or text == title:
                    continue

                if text not in clean_texts:
                    clean_texts.append(text)

            if clean_texts:
                result.append({
                    "title": title,
                    "values": clean_texts
                })

        if result:
            extracted["data"] = result

    except Exception as e:
        print(f"{section_type} мэдээлэл авахад алдаа: {e}")

    return extracted


if __name__ == "__main__":
    asyncio.run(scrape_facebook_profile())