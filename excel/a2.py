import asyncio
import json
from playwright.async_api import async_playwright

# Таны өгсөн cookie стринг
COOKIE_STRING = """
    datr=0f4TaniQolJ5C4YoG81CwSqZ;
    sb=0f4Tag_szj9t082e8Bc6butW;
    c_user=100021418158790;
    xs=8%3AwLNtoHNhRy9koA%3A2%3A1787020295%3A-1%3A-1%3A%3AAcyvqfjbt-IgAMHdHX-AvrptEwMX6lHrGhN5FFuwSoU;
    fr=1P2hYmneQCWl1cSGg.AWdPCBhczRy3v8-9-_vvQ3_QNJpeCdjH-bON3SGj2_L4ICRTCjc.BqhChd..AAA.0.0.BqhChd.AWd-7UO_mcGF-MlKxBk3ZRRCXQA;
"""

# Жишээ нь танд ирсэн тоон ID (эсвэл ID-уудын жагсаалт)
USER_ID = "100021418158790"

# Тоон ID ашиглан хуудасны линкүүдийг динамикаар үүсгэх
URLS = {
    "intro": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_intro",
    "personal_details": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_personal_details",
    "work": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_work",
    "education": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_education",
    "hobbies": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_activites",
    "interests": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_interests",
    "travel": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_travel",
    "links": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_links",
    "contact_info": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_contact_info",
    "names": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=directory_names",
    "aboutyou": f"https://www.facebook.com/profile.php?id={USER_ID}&sk=about_details"
}


def parse_cookies(cookie_string, domain=".facebook.com"):
    """Cookie-н стрингийг Playwright-д зориулсан dictionary формат руу хөрвүүлэх функц"""
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

        # Cookie-г хөтөчийн context рүү нэмэх
        formatted_cookies = parse_cookies(COOKIE_STRING)
        await context.add_cookies(formatted_cookies)

        page = await context.new_page()
        scraped_data = {}

        for key, url in URLS.items():
            print(f"[{key}] руу орж байна: {url}")
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(4000)  # Ачаалагдахыг хүлээнэ

                # Мэдээлэл шүүж авах функц дуудах
                data = await extract_data_by_section(page, key)
                scraped_data[key] = data

            except Exception as e:
                print(f"Алдаа гарлаа {key}: {e}")
                scraped_data[key] = None

        await browser.close()
        
        # Цуглуулсан өгөгдлийг цэгцэлж хэвлэх болон файл руу хадгалах функц дуудах
        print_and_save_scraped_data(scraped_data)
        
        return scraped_data


async def extract_data_by_section(page, section_type):
    """Facebook профайлаас зөвхөн шаардлагатай мэдээллийг авах"""

    extracted = {}

    # =========================================================
    # 1. BIO
    # =========================================================
    if section_type == "intro":

        try:
            bio_heading = page.locator('h2').filter(has_text="Bio").first

            if await bio_heading.count() > 0:

                section = bio_heading.locator(
                    "xpath=ancestor::section[1]"
                )

                # Bio-ийн бодит текст
                bio_locator = section.locator(
                    'div[dir="auto"][style*="text-align"]'
                ).first

                if await bio_locator.count() > 0:

                    bio = (await bio_locator.inner_text()).strip()

                    if bio:
                        extracted["bio"] = bio
                    else:
                        extracted["bio"] = None

                else:
                    extracted["bio"] = None

            else:
                extracted["bio"] = None

        except Exception as e:
            print(f"Bio авахад алдаа: {e}")
            extracted["bio"] = None


    # =========================================================
    # 2. PERSONAL DETAILS
    # =========================================================
    elif section_type == "personal details":

        try:
            # -------------------------
            # Location
            # -------------------------
            location_locator = page.locator(
                'section:has(h2:text("Location")) span[dir="auto"]'
            )

            if await location_locator.count() > 0:

                location = (
                    await location_locator.first.inner_text()
                ).strip()

                if location:
                    extracted["location"] = location
                else:
                    extracted["location"] = None

            else:
                extracted["location"] = None


            # -------------------------
            # Birthday
            # -------------------------
            birthday_section = page.locator(
                'section:has(h2:text("Birthday"))'
            )

            if await birthday_section.count() > 0:

                b_texts = await birthday_section.locator(
                    'span[dir="auto"]'
                ).all_inner_texts()

                valid_b_texts = []

                for text in b_texts:

                    text = text.strip()

                    if not text:
                        continue

                    if "Birth" in text:
                        continue

                    if "Shared" in text:
                        continue

                    if "Edit" in text:
                        continue

                    valid_b_texts.append(text)

                if valid_b_texts:
                    extracted["birthday"] = ", ".join(
                        valid_b_texts
                    )
                else:
                    extracted["birthday"] = None

            else:
                extracted["birthday"] = None


            # -------------------------
            # Gender
            # -------------------------
            gender_locator = page.locator(
                'section:has(h2:text("Gender")) span[dir="auto"]'
            )

            if await gender_locator.count() > 0:

                gender = (
                    await gender_locator.first.inner_text()
                ).strip()

                if gender:
                    extracted["gender"] = gender
                else:
                    extracted["gender"] = None

            else:
                extracted["gender"] = None


        except Exception as e:

            print(
                f"Personal details авахад алдаа: {e}"
            )


    # =========================================================
    # 3. OTHER SECTIONS
    # =========================================================
    elif section_type in [
        "work",
        "education",
        "hobbies",
        "interests",
        "travel",
        "links",
        "contact_info",
        "names",
        "aboutyou"
    ]:

        try:

            main = page.locator("div[role='main']")

            # Section-ийн heading-үүдийг авах
            headings = main.locator("h2")

            result = []

            for i in range(await headings.count()):

                heading = headings.nth(i)

                title = (
                    await heading.inner_text()
                ).strip()

                if not title:
                    continue

                # Heading-ийн дараах section
                section = heading.locator(
                    "xpath=ancestor::section[1]"
                )

                if await section.count() == 0:
                    continue

                # Тухайн section-ийн text
                texts = await section.locator(
                    '[dir="auto"]'
                ).all_inner_texts()

                clean_texts = []

                for text in texts:

                    text = text.strip()

                    if not text:
                        continue

                    # Facebook UI текстүүдийг хасна
                    unwanted = [
                        "Shared with Public",
                        "Shared with Friends",
                        "Edit",
                        "Edit details",
                        "See more",
                        "See less"
                    ]

                    if text in unwanted:
                        continue

                    if text == title:
                        continue

                    if text not in clean_texts:
                        clean_texts.append(text)

                if clean_texts:

                    result.append({
                        "title": title,
                        "values": clean_texts
                    })

            extracted["data"] = result


        except Exception as e:

            print(
                f"{section_type} мэдээлэл авахад алдаа: {e}"
            )

            extracted["data"] = []


    return extracted


def print_and_save_scraped_data(scraped_data):

    print("\n" + "=" * 60)
    print(" 📊 ФЭЙСБҮҮК ПРОФАЙЛЫН ЦУГЛУУЛСАН МЭДЭЭЛЭЛ ")
    print("=" * 60)

    for section, data in scraped_data.items():

        print(f"\n📌 [{section.upper()}]")

        if not data:
            print("   • Мэдээлэл олдсонгүй")
            continue

        if isinstance(data, dict):

            for key, value in data.items():

                if value is None:
                    continue

                if isinstance(value, list):

                    for item in value:
                        print(f"   • {item}")

                else:
                    print(f"   • {key}: {value}")

        else:
            print(f"   • {data}")

    print("\n" + "=" * 60)

    filename = "facebook_profile_data.json"

    try:

        # None утгуудыг ч JSON-оос хасах
        cleaned_data = {}

        for section, data in scraped_data.items():

            if not data:
                continue

            if isinstance(data, dict):

                cleaned_section = {}

                for key, value in data.items():

                    if value is None:
                        continue

                    if value == "":
                        continue

                    if value == []:
                        continue

                    cleaned_section[key] = value

                if cleaned_section:
                    cleaned_data[section] = cleaned_section

            else:

                cleaned_data[section] = data

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                cleaned_data,
                f,
                ensure_ascii=False,
                indent=4
            )

        print(
            f"💾 JSON хадгаллаа: {filename}"
        )

    except Exception as e:

        print(
            f"⚠️ JSON хадгалахад алдаа: {e}"
        )


if __name__ == "__main__":
    asyncio.run(scrape_facebook_profile())