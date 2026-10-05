from flask import Flask, jsonify, request, render_template_string, send_file
import io
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
import asyncio
import re
from playwright.async_api import async_playwright

app = Flask(__name__)
app.json.sort_keys = False

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

def parse_count(text):
    if not text:
        return ""
    text = str(text).strip().upper().replace(",", "")
    try:
        if "B" in text:
            return str(int(float(text.replace("B", "")) * 1_000_000_000))
        elif "M" in text:
            return str(int(float(text.replace("M", "")) * 1_000_000))
        elif "K" in text:
            return str(int(float(text.replace("K", "")) * 1_000))
        else:
            match = re.search(r'\d+', text)
            return match.group(0) if match else text
    except:
        return text

async def scrape_single_page(context, user_id):
    """Нэг tab дээр тухайн user_id-ийн мэдээллийг цуглуулах функц"""
    page = await context.new_page()
    await page.route("**/*.{css,font,woff,woff2}", lambda route: route.abort())
    scraped_data = {}
    
    try:
        # 1. Үндсэн About хуудас
        await page.goto(f"https://www.facebook.com/profile.php?id={user_id}", timeout=40000)
        try:
            await page.wait_for_selector('span[dir="auto"] > div[role="button"][tabindex="0"]', timeout=10000)
        except:
            # Хэрэв элемент олдохгүй бол body гарч ирсэн эсэхийг шалгаад цааш үргэлжлүүлнэ
            await page.wait_for_selector('body', timeout=5000)

        full_page_text = await page.locator("body").inner_text()
        page_html = await page.content()

        displayname = ""
        name_elem = page.locator('span[dir="auto"] > div[role="button"][tabindex="0"]').first
        if await name_elem.count() > 0:
            displayname = (await name_elem.inner_text()).strip()

        username_match = re.search(r'"userVanity":"([^"]+)"', page_html)
        friends_match = re.search(r'([\d,\.KMB]+)\s+Friends', full_page_text, re.IGNORECASE)
        followers_match = re.search(r'([\d,\.KMB]+)\s+Followers', full_page_text, re.IGNORECASE)
        following_match = re.search(r'([\d,\.KMB]+)\s+Following', full_page_text, re.IGNORECASE)

        profile_pic = ""
        try:
            img_elem = page.locator('svg[role="img"]:not([aria-label="Your profile"]) image').first
            if await img_elem.count() > 0:
                profile_pic = await img_elem.get_attribute('xlink:href') or await img_elem.get_attribute('href')
        except:
            pass

        stats = {
            "displayname": displayname,
            "username": username_match.group(1) if username_match else "",
            "profile_pic": profile_pic or "",
            "friends": friends_match.group(1).replace(",", "") if friends_match else "",
            "followers": followers_match.group(1).replace(",", "") if followers_match else "",
            "following": following_match.group(1).replace(",", "") if following_match else "",
            "is_closed": "Yes" if any(x in full_page_text.lower() for x in ["locked her profile", "locked his profile", "profile is private"]) else "No"
        }
        scraped_data["stats"] = stats

    except Exception as e:
        print(f"ID {user_id} үндсэн хуудас руу ороход алдаа: {e}")
        await page.close()
        return user_id, scraped_data

    # 2. Personal Details хуудас
    personal_url = f"https://www.facebook.com/profile.php?id={user_id}&sk=directory_personal_details"
    try:
        await page.goto(personal_url, timeout=40000)
        try:
            await page.wait_for_selector("div[role='main'] h2", timeout=10000)
        except:
            await page.wait_for_selector("div[role='main']", timeout=5000)

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
            clean_texts = [t.strip() for t in texts if t.strip() and t.strip() not in ["Shared with Public", "Shared with Friends", "Edit", "Edit details", "See more", "See less", title]]

            if clean_texts:
                result.append({"title": title, "values": clean_texts})

        if result:
            scraped_data["personal_details"] = {"data": result}

    except Exception as e:
        print(f"ID {user_id} Personal details алдаа: {e}")

    await page.close() # Ажиллаж дуусаад тухайн tab-аа хаана
    return user_id, scraped_data

async def scrape_multiple_profiles(user_ids):
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        
        # Нэг ширхэг сесс (context) үүсгээд cookie-гээ оруулна
        context = await browser.new_context()
        await context.add_cookies(parse_cookies(COOKIE_STRING))

        # 5 ID-аар нь багцлаад ээлжлэн 5 tab-аар зэрэг шалгана
        for i in range(0, len(user_ids), 5):
            batch = user_ids[i:i + 5]
            tasks = [scrape_single_page(context, uid) for uid in batch]
            
            # Энэ хэсэгт тухайн 5 tab зэрэг ажиллаж дуусахыг хүлээнэ
            completed = await asyncio.gather(*tasks)
            for uid, data in completed:
                if data:
                    results[uid] = data

        await context.close()
        await browser.close()

    return results

def flatten_scraped_data(scraped_data, user_id):
    row = {
        "id": str(user_id),
        "username": "",
        "profile_pic": "",
        "displayname": "",
        "is_closed": "",
        "friends": "",
        "followers": "",
        "following": "",
        "location": "",
        "hometown": "",
        "birthday": "",
        "status": "",
        "gender": ""
    }

    stats = scraped_data.get("stats", {})
    for k in row.keys():
        if k in stats and stats[k]:
            val = str(stats[k])
            if k in ["friends", "followers", "following"]:
                row[k] = parse_count(val)
            else:
                row[k] = val

    personal_data = scraped_data.get("personal_details", {}).get("data", [])
    for item in personal_data:
        title = str(item.get("title", "")).strip().lower()
        values = item.get("values", [])
        value = " | ".join(str(x).strip() for x in values if str(x).strip())
        if not value:
            continue

        if "live" in title or "current" in title or "location" in title:
            row["location"] = value.split(" | ")[0]
        elif "from" in title or "hometown" in title:
            row["hometown"] = value.split(" | ")[0]
        elif "birth" in title:
            month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', value, re.IGNORECASE)
            day_match = re.search(r'\b(0?[1-9]|[12][0-9]|3[01])\b', value)
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', value)
            if month_match and day_match:
                months = {
                    'january': '01', 'february': '02', 'march': '03', 'april': '04',
                    'may': '05', 'june': '06', 'july': '07', 'august': '08',
                    'september': '09', 'october': '10', 'november': '11', 'december': '12'
                }
                m_str = months.get(month_match.group(1).lower(), '01')
                d_str = day_match.group(1).zfill(2)
                y_str = year_match.group(1) if year_match else ""
                row["birthday"] = f"{y_str}-{m_str}-{d_str}" if y_str else f"{m_str}-{d_str}"
            else:
                row["birthday"] = value
        elif "status" in title or "relationship" in title:
            parts = [p.strip() for p in value.split("|") if p.strip()]
            row["status"] = " | ".join(dict.fromkeys(parts))
        elif "gender" in title or "sex" in title:
            row["gender"] = value

    return row

HTML = r'''<!DOCTYPE html>
<html lang="mn">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>FB Multi-ID Scraper (Fast Batch)</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f0f2f5;min-height:100vh;padding:30px 16px}
.card{background:#fff;border-radius:16px;padding:28px;max-width:1500px;margin:auto;box-shadow:0 4px 24px rgba(0,0,0,.1)}
.logo{color:#1877f2;font-size:26px;font-weight:700;text-align:center}
.sub{color:#888;text-align:center;margin:6px 0 20px;font-size:13px}
.input-wrap{margin-bottom:15px}
textarea{width:100%;height:100px;padding:12px 16px;border:2px solid #e0e0e0;border-radius:10px;font-size:14px;outline:none;resize:vertical}
textarea:focus{border-color:#1877f2}
.main-btn{width:100%;padding:13px 24px;background:#1877f2;color:#fff;border:0;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer}
.main-btn:hover{background:#1565c0}
.main-btn:disabled{background:#a9c5ee;cursor:not-allowed}
.status{margin-top:12px;color:#777;font-size:13px;min-height:20px;text-align:center}
.toolbar{display:none;gap:8px;margin-top:16px}
.tool-btn{padding:9px 14px;border:1px solid #1877f2;border-radius:8px;background:#f0f6ff;color:#1877f2;cursor:pointer;font-weight:600}
.table-wrap{display:none;margin-top:14px;border:1px solid #e2e2e2;border-radius:10px;overflow:auto;max-height:600px}
table{border-collapse:collapse;width:max-content;min-width:100%}
th{position:sticky;top:0;background:#1877f2;color:#fff;padding:10px;text-align:left;font-size:13px;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid #eee;font-size:13px;white-space:nowrap;max-width:400px;overflow:hidden;text-overflow:ellipsis}
tr:hover td{background:#f7faff}
.empty{color:#bbb}
</style>
</head>
<body>
<div class="card">
<div class="logo">FB Profile Scraper - Fast Batch</div>
<div class="sub">Нэг браузер сессээр шуурхай шалгах (Хамгийн ихдээ 200 ID)</div>

<div class="input-wrap">
<textarea id="userIdsInput" placeholder="ID-уудаа мөр мөрөөр эсвэл таслалаар тусгаарлаад оруулна уу (Max 200)..."></textarea>
</div>
<button class="main-btn" id="scrapeBtn" onclick="startScraping()">Цуглуулах</button>

<div class="status" id="status"></div>

<div class="toolbar" id="toolbar">
<button class="tool-btn" onclick="downloadExcel()">📥 Excel татах</button>
</div>

<div class="table-wrap" id="tableWrap">
<table>
<thead id="thead"></thead>
<tbody id="tbody"></tbody>
</table>
</div>
</div>

<script>
let rows=[],headers=[];

function setStatus(t){ document.getElementById("status").textContent=t; }

async function startScraping(){
    const rawText = document.getElementById("userIdsInput").value.trim();
    if(!rawText){ setStatus("⚠️ Хамгийн багадаа нэг ID оруулна уу."); return; }

    const ids = rawText.split(/[\n,\s]+/).map(id => id.trim()).filter(id => /^\d+$/.test(id));
    if(ids.length === 0){ setStatus("⚠️ Хүчинтэй тоон Facebook ID олдсонгүй."); return; }

    const btn = document.getElementById("scrapeBtn");
    btn.disabled = true;
    rows = [];
    document.getElementById("toolbar").style.display = "none";
    document.getElementById("tableWrap").style.display = "none";

    setStatus(`⏳ Броузер нээгдэж, ${ids.length} профайлын мэдээллийг цуглуулж байна... Түр хүлээнэ үү.`);

    try {
        const res = await fetch("/scrape-batch", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({user_ids: ids})
        });
        const data = await res.json();
        if(data.ok){
            rows = data.rows;
            renderTable();
            if(rows.length > 0){
                document.getElementById("toolbar").style.display = "flex";
                document.getElementById("tableWrap").style.display = "block";
            }
            setStatus(`✓ Нийт ${rows.length} профайлын мэдээлэл амжилттай цугларлаа.`);
        } else {
            setStatus(`❌ Алдаа гарлаа: ${data.error}`);
        }
    } catch(e) {
        console.error(e);
        setStatus(`❌ Холболтын алдаа гарлаа.`);
    }

    btn.disabled = false;
}

function renderTable(){
    if(rows.length === 0) return;
    const thead = document.getElementById("thead");
    const tbody = document.getElementById("tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";
    headers = Object.keys(rows[0]);

    const trh = document.createElement("tr");
    headers.forEach(h => {
        const th = document.createElement("th");
        th.textContent = h;
        trh.appendChild(th);
    });
    thead.appendChild(trh);

    rows.forEach(row => {
        const tr = document.createElement("tr");
        headers.forEach(h => {
            const td = document.createElement("td");
            const v = row[h] || "";
            td.textContent = v || "—";
            if(!v) td.className = "empty";
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

function downloadExcel(){
    if(!rows.length) return;
    fetch("/download-excel", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({rows: rows})
    })
    .then(r => r.blob())
    .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "facebook_profile_data.xlsx";
        a.click();
        a.remove();
    });
}
</script>
</body>
</html>'''

@app.get("/")
def index():
    return render_template_string(HTML)

@app.post("/scrape-batch")
def scrape_batch():
    data = request.get_json(silent=True) or {}
    user_ids = data.get("user_ids", [])
    user_ids = [str(uid).strip() for uid in user_ids if str(uid).strip().isdigit()][:200]

    if not user_ids:
        return jsonify({"ok": False, "error": "Хүчинтэй ID олдсонгүй."}), 400

    try:
        all_scraped = asyncio.run(scrape_multiple_profiles(user_ids))
        rows = []
        for uid in user_ids:
            if uid in all_scraped:
                row = flatten_scraped_data(all_scraped[uid], uid)
                rows.append(row)
        return jsonify({"ok": True, "rows": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/download-excel")
def download_excel():
    data = request.get_json(silent=True) or {}
    rows = data.get("rows", [])
    if not rows:
        return jsonify({"ok": False, "error": "Мэдээлэл алга."}), 400
        
    headers = list(rows[0].keys())
    wb = Workbook()
    ws = wb.active
    ws.title = "Facebook Data"
    ws.append(headers)

    for row in rows:
        ws.append([row.get(h, "") for h in headers])

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    for i, h in enumerate(headers, 1):
        max_len = len(str(h))
        for cell in ws[get_column_letter(i)]:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(i)].width = min(max(max_len + 2, 12), 45)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)

    return send_file(
        out,
        as_attachment=True,
        download_name="facebook_profile_data.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)