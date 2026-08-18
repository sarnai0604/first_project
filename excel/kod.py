import re
import itertools
import threading
from flask import Flask, request, jsonify, send_from_directory
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor
import os
 
app = Flask(__name__, static_folder='static')
 
COOKIES = [
    'datr=hqKFaDtm82hAyDfuetyPIalb; ps_l=1; ps_n=1; c_user=100061853225683; '
    'xs=34%3AEctKvWF7W-Cy9w%3A2%3A1781589221%3A-1%3A-1%3A%3AAcz_GN69reo1M9mtFkiqGtK4cPbo3Vv-dOP0Sk_U-g; '
    'presence=C%7B%22lm3%22%3A%22g.9081329378643002%22%2C%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781589230271%2C%22v%22%3A1%7D; wd=150x739; '
    'fr=1p182QbymWbpeswu9.AWf30lUn5-qPZpDuK8cLIbLR6-KBdYMgXY08JgIQNS8O7gqj4_g.BqMOTo..AAA.0.0.BqMOTo.AWffJxKI3J177TmxJKIJW4b8YN0'
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
 
# ── Gone / deactivated helpers (app.py-тай ижил) ─────────────
def _extract_location(html):
    m = re.search(
        r'"text"\s*:\s*\{\s*"text"\s*:\s*"(?:Lives in|From)\s+([^"]+)"',
        html
    )
    if m:
        return m.group(1).strip()
    m = re.search(
        r'"text"\s*:\s*"(?:Lives in|From)\s+([^"]+)"',
        html
    )
    if m:
        return m.group(1).strip()
    return ''

def _is_gone(resp):
    if resp.status_code == 404:
        return True
    url = resp.url
    if '/home.php' in url or url.rstrip('/').endswith('facebook.com'):
        return True
    return False

def _is_deactivated(text):
    m = re.search(r'"isAdminViewingDeactivatedProfile"\s*:\s*(\w+)', text)
    return bool(m and m.group(1) != 'null')

# ── Core lookup ───────────────────────────────────────────────
def do_lookup(q):
    session = get_session()
    # Хоосон буцаах бэлдэц
    empty_res   = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": "", "is_closed": "", "is_deleted": "", "location": ""}
    deleted_res = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": "", "is_closed": "", "is_deleted": "-", "location": ""}
   
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

        # ── 1. Cookie үхэж login руу шидсэн ──
        if 'login' in resp.url or 'checkpoint' in resp.url:
            return empty_res

        # ── 2. Устсан профайл шалгах (app.py-тай ижил) ──
        if _is_gone(resp) or _is_deactivated(html_content):
            return deleted_res
       
        friends = followers = following = ''

        # Friends — JSON эхлээд, дараа HTML
        m = re.search(r'"friend_count"\s*:\s*(\d+)', html_content)
        if m:
            friends = m.group(1)
        else:
            m = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:friends|найз)', html_content, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val.replace('.','').replace(',','').replace('K','').replace('k','').replace('M','').replace('m',''):
                    friends = val

        # Followers — JSON эхлээд, дараа HTML
        m = re.search(r'"subscriber_count"\s*:\s*(\d+)', html_content)
        if not m:
            m = re.search(r'"follower_count"\s*:\s*(\d+)', html_content)
        if m:
            followers = m.group(1)
        elif not friends:
            m = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:followers|дагагч)', html_content, re.IGNORECASE)
            if m:
                followers = m.group(1).strip()

        # Following
        m = re.search(r'"following_count"\s*:\s*(\d+)', html_content)
        if not m:
            m = re.search(r'"text"\s*:\s*"([\d.,KkMm]+)\s*following"', html_content, re.IGNORECASE)
        if not m:
            m = re.search(r'>([\d.,KkMm]+)<\/strong>\s*following', html_content, re.IGNORECASE)
        if not m:
            m = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*following', html_content, re.IGNORECASE)
        if m:
            following = m.group(1)
        # Followers байвал following заавал байх ёстой — loose fallback
        if followers and not following:
            m = re.search(r'([\d.,KkMm]+)\s*following', html_content, re.IGNORECASE)
            if m:
                following = m.group(1)
 
        profile_valid = bool(slug) if q.isdigit() else bool(fb_id)

        # ── Gender ───────────────────────────────────────────
        gender = ''
        if profile_valid:
            m_gender = re.search(r'"\s*,\s*"gender"\s*:\s*"?(\w+)"?', html_content)
            if m_gender:
                raw = m_gender.group(1).lower()
                if raw == 'male':
                    gender = 'male'
                elif raw == 'female':
                    gender = 'female'
                elif raw == 'neuter':
                    gender = 'neuter'

        # ── Locked / Open ─────────────────────────────────
        if ('"LockedProfileTryItBanner"' in html_content
                or 'locked her profile' in html_content
                or 'locked his profile' in html_content
                or 'locked their profile' in html_content):
            is_closed = 'locked'
        elif profile_valid and (friends or followers or following):
            is_closed = 'open'
        else:
            is_closed = ''

        return {
            "username":  slug,
            "id":        fb_id,
            "friends":   friends,
            "followers": followers,
            "following": following,
            "gender":    gender,
            "is_closed": is_closed,
            "is_deleted": "",
            "location":  _extract_location(html_content),
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