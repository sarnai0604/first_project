import re
import itertools
import threading
from flask import Flask, request, jsonify, send_from_directory
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__, static_folder='static')

COOKIES = [
    'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100021418158790; '
    'xs=23%3AwFJABj_vU7RCKw%3A2%3A1779695328%3A-1%3A-1%3A%3AAcy9GiVlisEoz9oluJq_cPViIpp3m57DIABrmF_GP94; '
    'presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781233195055%2C%22v%22%3A1%7D; wd=150x828; '
    'fr=1ySmBbI4Yg99LH2FS.AWf196ghAANvuHHNqEa17HldXXxgJzHzBQI2PwWFgwTA6WcmSK8.BqK3S3..AAA.0.0.BqK3YR.AWcaUMtM8qq4wCETmNWE_blMXVc'
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

# ── Core lookup ───────────────────────────────────────────────
def do_lookup(q):
    session = get_session()
    # Хоосон буцаах бэлдэц
    empty_res = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": ""}
    
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
                timeout=15
            )
            m = re.search(r'"userID":"(\d+)"', resp.text)
            fb_id = m.group(1) if m else ''
            slug = q

        html_content = resp.text

        # ── 1. Устсан эсвэл хаагдсан хаяг эсэхийг шалгах ──
        if "This content isn't available right now" in html_content or "This Content Isn't Available Right Now" in html_content:
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
            if not m_followers:
                m_followers = re.search(r'([\d.,KkMm]+)\s*(?:followers|дагагч)', html_content, re.IGNORECASE)
            if m_followers:
                followers = m_followers.group(1).strip()

            m_following = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:following|дагаж)', html_content, re.IGNORECASE)
            if not m_following:
                m_following = re.search(r'([\d.,KkMm]+)\s*(?:following|дагаж)', html_content, re.IGNORECASE)
            if m_following:
                following = m_following.group(1).strip()

        # ── Gender ───────────────────────────────────────────
        gender = '' # Өмнө нь 'unknown' байсныг хоосон үлдээдэг болгов
        m_gender = re.search(r'"\s*,\s*"gender"\s*:\s*"?(\w+)"?', html_content)
        if m_gender:
            raw = m_gender.group(1).lower()
            if raw in ('male', '1', 'men', 'MALE'):
                gender = 'male'
            elif raw in ('female', '2', 'women', 'FEMALE'):
                gender = 'female'
            elif raw == 'neuter':
                gender = 'neuter'

        return {
            "username":  slug,
            "id":        fb_id,
            "friends":   friends,
            "followers": followers,
            "following": following,
            "gender":    gender
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
    app.run(host='0.0.0.0', port=9090, debug=True, threaded=True)