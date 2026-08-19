import asyncio
import json
import re
from playwright.async_api import async_playwright

COOKIE_STRING = """
    datr=0f4TaniQolJ5C4YoG81CwSqZ;
    sb=0f4Tag_szj9t082e8Bc6butW;
    c_user=100021418158790;
    xs=8%3AwLNtoHNhRy9koA%3A2%3A1787020295%3A-1%3A-1%3A%3AAcypOVMrf1M7y489HxpzwRWRSEIjWLq4jhiJpAQd8sg;
    fr=1RkXXYMkcdsrbAF8d.AWe4V8BlEYaUmTP2MXpu29DxhN6H3268iGPOqipvrXIAyZ8oOHY.BqhRj3..AAA.0.0.BqhRj3.AWds7aShSaZLyZG1UjoEOVXKtH8;
"""

USER_ID = "100054640671737"

URL_MAPPING = {
    "intro": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_intro",
    "category": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_category",
    "personal_details": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_personal_details",
    "work": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_work",
    "education": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_education",
    "links": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_links",
    "contact_info": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_contact_info"
}

def parse_cookies(cookie_string, domain=".facebook.com"):
    cookies = []
    parts = cookie_string.strip().split(";")
    for part in parts:
        if "=" in part:
            name, value = part.strip().split("=", 1)
            cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return cookies

async def scrape_facebook_profile():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        formatted_cookies = parse_cookies(COOKIE_STRING)
        await context.add_cookies(formatted_cookies)

        page = await context.new_page()
        scraped_data = {}

        # 1. Профайлын About хуудас руу орох
        main_about_url = f"https://www.facebook.com/profile.php?id={USER_ID}&sk=about"
        print(f"[Үндсэн About] хуудас руу орж байна: {main_about_url}")
        
        try:
            await page.goto(main_about_url, timeout=60000)
            await page.wait_for_timeout(4000)

            # HTML болон текстийг бүтнээр нь авах
            html_content = await page.content()
            full_page_text = await page.locator("body").inner_text()
            
            stats = {}

            # ── Locked / Open ─────────────────────────────────
            if ('"LockedProfileTryItBanner"' in html_content
                    or 'locked her profile' in html_content
                    or 'locked his profile' in html_content
                    or 'locked their profile' in html_content):
                stats["is_closed"] = 'locked'
            else:
                stats["is_closed"] = 'open'

            # Хуудасны үндсэн текстээс stats (friends, followers, following, likes) шүүж авах
            friends_match = re.search(r'([\d,\.KMB]+)\s+Friends', full_page_text, re.IGNORECASE)
            followers_match = re.search(r'([\d,\.KMB]+)\s+Followers', full_page_text, re.IGNORECASE)
            following_match = re.search(r'([\d,\.KMB]+)\s+Following', full_page_text, re.IGNORECASE)
            likes_match = re.search(r'([\d,\.KMB]+)\s+Likes', full_page_text, re.IGNORECASE)

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

            # 2. <div class="x1yztbdb"> контейнерээс цэснүүдийг шалгаж олох
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
                
                print(f"Олдсон цэсний нэрс (<div class=\"x1yztbdb\">): {found_texts}")

                mapping_keywords = {
                    "intro": "intro",
                    "category": "category",
                    "personal details": "personal_details",
                    "work": "work",
                    "education": "education",
                    "links": "links",
                    "contact info": "contact_info"
                }

                for key_phrase, url_key in mapping_keywords.items():
                    if any(key_phrase in ft for ft in found_texts):
                        active_keys.add(url_key)

            if not active_keys:
                active_keys = {"intro", "category", "contact_info"}

            print(f"Шалгаж үзэх идэвхтэй секцүүд: {active_keys}")

            # 3. Зөвхөн илэрсэн секцүүд рүүгээ л дараалж орж мэдээлэл татах
            for key in active_keys:
                if key not in URL_MAPPING:
                    continue
                url = URL_MAPPING[key]
                print(f"[{key}] секц рүү орж байна: {url}")
                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_timeout(3000)

                    data = await extract_data_by_section(page, key)
                    if data:
                        scraped_data[key] = data
                except Exception as e:
                    print(f"Алдаа гарлаа {key}: {e}")

        except Exception as e:
            print(f"Үндсэн хуудас руу ороход алдаа гарлаа: {e}")

        await browser.close()
        print_and_save_scraped_data(scraped_data)
        return scraped_data


async def extract_data_by_section(page, section_type):
    extracted = {}
    
    # 1. Ерөнхий мэдээллийн блокуудыг авах
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

            # 2. Хэрэв section_type нь "intro" бол data дотроос 'bio'-г ялгаж авах (давхардалгүй)
            # if section_type == "intro":
            #     for item in result:
            #         if item["title"].lower() == "bio":
            #             extracted["bio"] = item["values"][0]
            #             break

    except Exception as e:
        print(f"{section_type} мэдээлэл авахад алдаа: {e}")

    return extracted


def print_and_save_scraped_data(scraped_data):
    print("\n" + "=" * 60)
    print(" 📊 ФЭЙСБҮҮК ПРОФАЙЛЫН ЦУГЛУУЛСАН МЭДЭЭЛЭЛ ")
    print("=" * 60)

    filename = "facebook_profile_data.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=4)
        print(f"💾 JSON амжилттай хадгаллаа: {filename}")
    except Exception as e:
        print(f"⚠️ JSON хадгалахад алдаа: {e}")

if __name__ == "__main__":
    asyncio.run(scrape_facebook_profile())