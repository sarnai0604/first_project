from playwright.sync_api import sync_playwright

PROFILE_ID = "100021418158790"

COOKIE_STRING = """
datr=0f4TaniQolJ5C4YoG81CwSqZ;
sb=0f4Tag_szj9t082e8Bc6butW;
c_user=100021418158790;
xs=8%3AwLNtoHNhRy9koA%3A2%3A1787020295%3A-1%3A-1%3A%3AAcy5Cwyf15Wagltzd31D5LUMi0qHGiwfzAILRtNSMw;
fr=1XRU4RhVu9OG764MR.AWcnPYEdTz8TdeTMVUN5PBECRQ4yWxKhaW9ipDm7rDhWfQrrgpA.BqhAOR..AAA.0.0.BqhAOR.AWfFcCe920iW2dLmtatHdxe1tds;
"""

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context()

    # Cookie string -> Playwright cookies
    cookies = []

    for item in COOKIE_STRING.split(";"):
        item = item.strip()

        if not item:
            continue

        name, value = item.split("=", 1)

        cookies.append({
            "name": name,
            "value": value,
            "domain": ".facebook.com",
            "path": "/"
        })

    # Cookie-г browser context-д суулгана
    context.add_cookies(cookies)

    page = context.new_page()

    url = f"https://www.facebook.com/{PROFILE_ID}"

    print(f"Opening: {url}")

    try:

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print(
            "HTTP status:",
            response.status if response else "Unknown"
        )

        print("Final URL:", page.url)

        # JS ачаалуулах
        page.wait_for_timeout(5000)

        print("Title:", page.title())

        # Бүтэн DOM HTML
        html = page.content()

        print(f"HTML length: {len(html):,}")

        filename = f"facebook_{PROFILE_ID}.html"

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(html)

        print(f"Saved: {filename}")

    except Exception as e:
        print("ERROR:", e)

    finally:
        browser.close()