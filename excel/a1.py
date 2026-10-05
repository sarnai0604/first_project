import re
import itertools
import threading
from flask import Flask, request, jsonify, send_from_directory
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__, static_folder='static')

COOKIE = 'datr=wKZxasZ8H2EYPmRcUZZ6jNUl; sb=nqRyaoOHiizb_L44rJuYB99H; ps_l=1; ps_n=1; c_user=61593179188492; xs=20%3AGFxhX5ft21_thw%3A2%3A1786330706%3A-1%3A-1%3A%3AAcyOzgXqX5gRu0tP1rBQiaiFnPySRrCeL4TGtce6ejI; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1787717449345%2C%22v%22%3A1%7D'
   

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


SESSION = cf_requests.Session(
    impersonate='chrome120'
)

# ── Cookie rotate ─────────────────────────────────────────────
def get_headers():
    return {
        'User-Agent': USER_AGENT,
        'Cookie': COOKIE
    }

# ── Location extract (Lives in & From) ────────────────────────
def _extract_locations(html):
    lives_in = ''
    from_place = ''

    # 1. Lives in хайх
    m_lives = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if not m_lives:
        m_lives = re.search(r'"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if m_lives:
        lives_in = m_lives.group(1).strip()

    # 2. From хайх
    m_from = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"From\s+([^"]+)"', html)
    if not m_from:
        m_from = re.search(r'"text"\s*:\s*"From\s+([^"]+)"', html)
    if m_from:
        from_place = m_from.group(1).strip()

    return lives_in, from_place



# ── Relationship Status extract ───────────────────────────────
def _extract_status(html):
    # Facebook relationship status нь ихэвчлэн:
    # <span ...>Married</span>
    # <span ...>Single</span>
    # гэх мэтээр гардаг.

    status_patterns = [
        (r'>\s*Married\s*<', 'married'),
        (r'>\s*Engaged\s*<', 'engaged'),
        (r'>\s*In a relationship\s*<', 'in a relationship'),
        (r'>\s*Separated\s*<', 'separated'),
        (r'>\s*Divorced\s*<', 'divorced'),
        (r'>\s*Single\s*<', 'single'),

        # Монгол хэл дээр гарч болох хувилбарууд
        (r'>\s*Гэрлэсэн\s*<', 'married'),
        (r'>\s*Сүй тавьсан\s*<', 'engaged'),
        (r'>\s*Үерхдэг\s*<', 'in a relationship'),
        (r'>\s*Тусдаа амьдардаг\s*<', 'separated'),
        (r'>\s*Салсан\s*<', 'divorced'),
        (r'>\s*Ганц бие\s*<', 'single'),
    ]

    for pattern, value in status_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return value

    return ''


def _extract_category(html):
    from html import unescape

    pattern = re.compile(
        r'<div[^>]*role=["\']button["\'][^>]*>'
        r'\s*([^<]+?)'
        r'\s*<div[^>]*role=["\']none["\']',
        re.IGNORECASE | re.DOTALL
    )

    for m in pattern.finditer(html):
        value = unescape(m.group(1)).strip()

        if value:
            return value

    return ''




# ── Core lookup (ID Only) ─────────────────────────────────────
def do_lookup(q):
    empty_res = {
        "username": "", 
        "id": "", 
        "friends": "", 
        "followers": "", 
        "following": "", 
        "gender": "", 
        "is_closed": "", 
        "lives_in": "", 
        "from_place": "",
        "status": "",
        "category": ""
    }

    # Хэрэв оруулсан утга тоон ID биш бол шууд буцаана
    if not q.isdigit():
        return empty_res

    try:
        headers = get_headers()
        resp = SESSION.get(
            f'https://www.facebook.com/{q}',
            headers=headers,
            timeout=10,
            allow_redirects=True
        )

        # Cookie үхэж login руу шидсэн эсэх
        if 'login' in resp.url or 'checkpoint' in resp.url:
            return empty_res

        final_url = resp.url.rstrip('/').split('?')[0].split('#')[0]
        slug = final_url.split('facebook.com/')[-1].strip('/')
        if not (slug and slug != q and not slug.isdigit() and re.match(r'^[\w.]+$', slug)):
            slug = ''
        fb_id = q

        html_content = resp.text

        friends = followers = following = ''


        # Friends
        m_friends = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:friends|найз)', html_content, re.IGNORECASE)
        if not m_friends:
            m_friends = re.search(r'([\d.,KkMm]+)\s*(?:friends|найз)', html_content, re.IGNORECASE)
        if m_friends:
            clean = m_friends.group(1).strip().replace('.', '').replace(',', '')
            if clean and any(c.isalnum() for c in clean):
                friends = m_friends.group(1).strip()


        # Followers (Холбоос хамаарахгүйгээр тусад нь хайна)
        m_followers = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:followers|дагагч)', html_content, re.IGNORECASE)
        if not m_followers:
            m_followers = re.search(r'([\d.,KkMm]+)\s*(?:followers|дагагч)}', html_content, re.IGNORECASE)
        if m_followers:
            followers = m_followers.group(1).strip()


        # Following (Холбоос хамаарахгүйгээр тусад нь хайна)
        m_following = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:following|дагаж)', html_content, re.IGNORECASE)
        if not m_following:
            m_following = re.search(r'([\d.,KkMm]+)\s*(?:following|дагаж)', html_content, re.IGNORECASE)
        if m_following:
            following = m_following.group(1).strip()


        # ── Gender ───────────────────────────────────────────
        gender = ''
        m_gender = re.search(r'"\s*,\s*"gender"\s*:\s*"?(\w+)"?', html_content)
        if m_gender:
            raw = m_gender.group(1).lower()
            if raw in ['male', 'female', 'neuter', 'unknown']:
                gender = raw
            else:
                gender = ''

        # ── Locked / Open ─────────────────────────────────
        if ('"LockedProfileTryItBanner"' in html_content
                or 'locked her profile' in html_content
                or 'locked his profile' in html_content
                or 'locked their profile' in html_content):
            is_closed = 'locked'
        else:
            is_closed = 'open'

        # ── Lives in & From ───────────────────────────────
        lives_in, from_place = _extract_locations(html_content)


        return {
            "username":   slug,
            "id":         fb_id,
            "friends":    friends,
            "followers":  followers,
            "following":  following,
            "gender":     gender,
            "is_closed":  is_closed,
            "lives_in":   lives_in,
            "from_place": from_place,
            "status":       _extract_status(html_content),
            "category":     _extract_category(html_content)
        }

    except Exception as e:
        print("LOOKUP ERROR:", e)
        return empty_res

# ── Routes ────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/batch', methods=['POST'])
def batch():
    data  = request.get_json(silent=True) or {}
    items = [str(x).strip() for x in data.get('items', []) if str(x).strip()]
    if not items:
        return jsonify({'results': []})

    workers = min(15, len(items))
    print(f"ITEM COUNT: {len(items)}  |  WORKERS: {workers}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(do_lookup, items))

    return jsonify({'results': results})

@app.route('/lookup')
def lookup():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'result': {}})
    return jsonify({'result': do_lookup(q)})

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)

    try:
        app.run(
            host='0.0.0.0',
            port=8080,
            debug=False,
            threaded=True
        )

    except KeyboardInterrupt:
        print("\nStopping server...")

    finally:
        print("Closing Facebook session...")
        SESSION.close()
        print("Session closed.")