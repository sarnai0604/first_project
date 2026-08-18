import re
import itertools
import threading
from flask import Flask, request, jsonify, send_from_directory
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__, static_folder='static')

COOKIES = [
    'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100021418158790; xs=27%3A6-dgPTNn8bBmoA%3A2%3A1781750081%3A-1%3A-1%3A%3AAcy5MgsosQRJGoVvTvfMoZOJ0RUrvQ2murqkyd_HxA; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781682787314%2C%22v%22%3A1%7D; wd=290x794; fr=1ru5yWIlMHC1QBPo8.AWcc00Yx82PLRopluxlIav7yEpEUC8cke_IVdfNMxgolEgx3a54.BqM1lD..AAA.0.0.BqM1s0.AWcSKLu0NBVJqi83l-G_av2Bi9Y;',
    # 'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100090316622127; xs=19%3A7GZqlgVSWlAVgg%3A2%3A1781749946%3A-1%3A-1%3A%3AAcyqGZgPH5_4w-1syVQ29v-Vpi7xwHGS1xjoAzO0ag; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781749955177%2C%22v%22%3A1%7D; wd=290x794; fr=1SQ473Wh6QOGVDpX7.AWfaprKTtl9ibJptSXEXbFwzAmL0UWdyDXqWLHAtIUi-zKZ7GDE.BqM1jB..AAA.0.0.BqM1jG.AWc3mOQBXiNawT_JaozG5lCrK2Q;'
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
        if ('"LockedProfileTryItBanner"' in html_content
                or 'locked her profile' in html_content
                or 'locked his profile' in html_content
                or 'locked their profile' in html_content):
            is_closed = 'locked'
        else:
            is_closed = 'open'

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
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)