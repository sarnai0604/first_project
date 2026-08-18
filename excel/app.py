import re
import itertools
import threading
from flask import Flask, request, jsonify, send_from_directory
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__, static_folder='static')

COOKIES = [
    'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100021418158790; xs=15%3AT9wxyXhpayenaQ%3A2%3A1781849568%3A-1%3A-1%3A%3AAcw0iPVq4jM_KrPZ_Pd7CqpdvbEw25bjNpOeTgQ0Pw; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781682787314%2C%22v%22%3A1%7D; wd=222x798; fr=18ugmDKRiJVeylszy.AWfWGq1vyrZ5ZmIb63HNPpCn9ajPEGAUGyPUsNkHHcTZizFcbqg.BqNN3k..AAA.0.0.BqNN3k.AWc-26TpIuaGHT1HgOcPYLjTouA;',
    # 'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100090316622127; xs=25%3A7xb-yeWFobVodg%3A2%3A1781768771%3A-1%3A-1%3A%3AAcwSW3YtOOkoV0p3WNta20vecj269T7V1E38ODyKvg; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781749955177%2C%22v%22%3A1%7D; wd=255x794; fr=196UMTkDL03YyfVfR.AWen2OTmIqkrag2w6tRFisY8CdxVVNjlm8eepgAVqD8gxvCvp_E.BqM6JG..AAA.0.0.BqM6JG.AWd2OB0XUzT9HmxIdyIXimTnq0M;'
]

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

_cycle = itertools.cycle(COOKIES)
_cookie_lock = threading.Lock()

# ── Session pool ──────────────────────────────────────────────
_session_pool: list = []
_session_lock = threading.Lock()

def _new_session():
    return cf_requests.Session(impersonate='chrome120')

def get_session():
    with _session_lock:
        if _session_pool:
            return _session_pool.pop()
    return _new_session()

def release_session(s):
    with _session_lock:
        _session_pool.append(s)

# ── Cookie rotate ─────────────────────────────────────────────
def get_headers():
    with _cookie_lock:
        cookie = next(_cycle)
    return {'User-Agent': USER_AGENT, 'Cookie': cookie}

# ── Location extract ──────────────────────────────────────────
def _extract_location(html):
    # "Lives in ..." эсвэл "From ..." гэсэн текстийг JSON-оос олох
    # Хэлбэр: "text":"Lives in Ulaanbaatar" эсвэл "text":"From Mongolia"
    m = re.search(
        r'"text"\s*:\s*\{\s*"text"\s*:\s*"(?:Lives in|From)\s+([^"]+)"',
        html
    )
    if m:
        return m.group(1).strip()
    # Хялбаршуулсан хэлбэр: "text":"Lives in Ulaanbaatar"
    m = re.search(
        r'"text"\s*:\s*"(?:Lives in|From)\s+([^"]+)"',
        html
    )
    if m:
        return m.group(1).strip()
    return ''

# ── Core lookup ───────────────────────────────────────────────
def do_lookup(q):
    session = get_session()
    empty_res = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": "", "is_closed": "", "location": ""}

    try:
        headers = get_headers()

        if q.isdigit():
            resp = session.get(
                f'https://www.facebook.com/{q}',
                headers=headers,
                timeout=10,
                allow_redirects=True
            )
            final_url = resp.url.rstrip('/').split('?')[0].split('#')[0]
            slug = final_url.split('facebook.com/')[-1].strip('/')
            if not (slug and slug != q and not slug.isdigit() and re.match(r'^[\w.]+$', slug)):
                slug = ''
            fb_id = q
        else:
            resp = session.get(
                f'https://www.facebook.com/{q}',
                headers=headers,
                timeout=30
            )
            m = re.search(r'"userID":"(\d+)"', resp.text)
            fb_id = m.group(1) if m else ''
            slug = q

        html_content = resp.text

        # ── Cookie үхэж login руу шидсэн ──
        if 'login' in resp.url or 'checkpoint' in resp.url:
            return empty_res

        friends = followers = following = ''

        # Friends
        m_friends = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:friends|найз)', html_content, re.IGNORECASE)
        if not m_friends:
            m_friends = re.search(r'([\d.,KkMm]+)\s*(?:friends|найз)', html_content, re.IGNORECASE)
        if m_friends:
            clean = m_friends.group(1).strip().replace('.', '').replace(',', '')
            if clean and any(c.isalnum() for c in clean):
                friends = m_friends.group(1).strip()

        # Followers & Following
        if not friends:
            m_followers = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:followers|дагагч)', html_content, re.IGNORECASE)
            if m_followers:
                followers = m_followers.group(1).strip()

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
            if raw == 'male':
                gender = 'male'
            elif raw == 'female':
                gender = 'female'
            elif raw == 'neuter':
                gender = 'neuter'
            else:
                gender = 'unknown'

        # ── Locked / Open ─────────────────────────────────
        profile_valid = bool(slug) if q.isdigit() else bool(fb_id)

        if ('"LockedProfileTryItBanner"' in html_content
                or 'locked her profile' in html_content
                or 'locked his profile' in html_content
                or 'locked their profile' in html_content):
            is_closed = 'locked'
        elif profile_valid and (friends or followers or following):
            is_closed = 'open'
        else:
            is_closed = ''

        # ── Location ──────────────────────────────────────
        location = _extract_location(html_content)

        return {
            "username":  slug,
            "id":        fb_id,
            "friends":   friends,
            "followers": followers,
            "following": following,
            "gender":    gender,
            "is_closed": is_closed,
            "location":  location,
        }

    except Exception as e:
        print("LOOKUP ERROR:", e)
        return empty_res
    finally:
        release_session(session)

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
    app.run(host='0.0.0.0', port=7070, debug=True, threaded=True)