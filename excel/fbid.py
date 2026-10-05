import re
import itertools
import threading
import time
import random
from flask import Flask, request, jsonify, send_from_directory
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__, static_folder='static')

COOKIES = [
    #oko
    'datr=KOO5arE6ayAUWDYT9umPwITQ; ps_l=1; ps_n=1; c_user=61563545111550; '
    'xs=35%3AtZT35FHzY_uNpg%3A2%3A1790567253%3A-1%3A-1%3A%3AAcyVMKLWq3-N0Nycc8Qm8waQl-mOKnJkVuqW4dDC1Q;'
    'presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1785127214926%2C%22v%22%3A1%7D; wd=844x911; '
    'fr=1WfsqsoHdWQCYBUKd.AWdnSvfIQUscId3fwjvbicG59qKJ19ze4oswZ1OwH7qc4h9ntxc.BqueNa..AAA.0.0.BqueNa.AWdlwP9vXSdR6ynSAz3C2nssaTc; ',
]

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'

_cycle = itertools.cycle(COOKIES)
_cookie_lock = threading.Lock()

_session_pool = []
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

def get_headers():
    with _cookie_lock:
        cookie = next(_cycle)
    return {'User-Agent': USER_AGENT, 'Cookie': cookie}

def _parse_count(val):
    if not val:
        return val
    val = val.strip().replace(',', '')
    m = re.match(r'^([\d.]+)\s*([KkMm]?)$', val)
    if not m:
        return val
    num = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == 'K':
        num = 1000
    elif suffix == 'M':
        num = 1000000
    return str(int(num))

def _extract_location(html):
    for pat in [
        r'"text"\s:\s\{\s*"text"\s*:\s*"(?:Lives in|From)\s+([^"]{2,60})"',
        r'"text"\s*:\s*"(?:Lives in|From)\s+([^"]{2,60})"',
    ]:
        m = re.search(pat, html)
        if m:
            loc = m.group(1).strip()
            if not any(w in loc.lower() for w in ['now on', 'your', 'interaction', 'will be']):
                return loc
    return ''

def _is_gone(resp):
    if resp.status_code == 404:
        return True
    url = resp.url
    if '/home.php' in url or url.rstrip('/').endswith('facebook.com'):
        return True
    return False

def _is_deactivated(text):
    return '"isAdminViewingDeactivatedProfile"' in text

def do_lookup(q):
    session = get_session()
    empty_res  = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": "", "is_closed": "", "is_deleted": "", "location": ""}
    deleted_res = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": "", "is_closed": "", "is_deleted": "-", "location": ""}

    try:
        time.sleep(random.uniform(0.3, 1.0))
        headers = get_headers()

        if q.isdigit():
            resp = session.get(
                f'https://www.facebook.com/{q}',
                headers=headers,
                timeout=40,
                allow_redirects=True
            )
            final_url = resp.url.rstrip('/').split('?')[0].split('#')[0]
            slug = final_url.split('facebook.com/')[-1].strip('/')
            if not (slug and slug != q and not slug.isdigit() and re.match(r'^[\w.]+$', slug)) or slug == 'profile.php':
                slug = ''
            fb_id = q
        else:
            resp = session.get(
                f'https://www.facebook.com/{q}',
                headers=headers,
                timeout=30
            )
            m = (re.search(r'"userVanity":"[^"]+","userID":"(\d+)"', resp.text) or
                 re.search(r'"userID":"(\d{8,})"', resp.text))
            fb_id = m.group(1) if m else ''
            slug = q

        html_content = resp.text

        if 'login' in resp.url or 'checkpoint' in resp.url:
            return empty_res

        if _is_gone(resp) or _is_deactivated(html_content):
            return deleted_res

        profile_valid = bool(fb_id)
        friends = followers = following = gender = ''

        if profile_valid:
            # Friends
            m = re.search(r'html-strong[^>]*>([\d.,KkMm]+)<\/strong>\s*friends?', html_content, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val.replace('.','').replace(',','').replace('K','').replace('k','').replace('M','').replace('m',''):
                    friends = val

            # Followers & Following
            if not friends:
                m_followers = re.search(r'html-strong[^>]*>([\d.,KkMm]+)<\/strong>\s*followers?', html_content, re.IGNORECASE)
                if m_followers:
                    followers = m_followers.group(1).strip()

                m_following = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:following|дагаж)', html_content, re.IGNORECASE)
                if not m_following:
                    m_following = re.search(r'([\d.,KkMm]+)\s*(?:following|дагаж)', html_content, re.IGNORECASE)
                    if m_following:
                        following = m_following.group(1).strip()

            mg = re.search(r'"\s*,\s*"gender"\s*:\s*"?(\w+)"?', html_content)
            if mg:
                raw = mg.group(1).lower()
                if raw in ('male', 'female', 'neuter'):
                    gender = raw

        # Locked / Open               
        if ('"LockedProfileTryItBanner"' in html_content
                or 'locked her profile' in html_content
                or 'locked his profile' in html_content
                or 'locked their profile' in html_content):
            is_closed = 'locked'
        elif profile_valid and (friends or followers or following):
            is_closed = 'open'
        else:
            is_closed = ''

        result = {
            "username":   slug,
            "id":         fb_id,
            "friends":    _parse_count(friends),
            "followers":  _parse_count(followers),
            "following":  _parse_count(following),
            "gender":     gender,
            "is_closed":  is_closed,
            "is_deleted": "",
            "location":   _extract_location(html_content),
        }

        return result

    except Exception as e:
        print("LOOKUP ERROR:", str(e).split('See https://')[0].strip())
        return empty_res
    finally:
        release_session(session)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/batch', methods=['POST'])
def batch():
    data  = request.get_json(silent=True) or {}
    items = [str(x).strip() for x in data.get('items', []) if str(x).strip()]
    if not items:
        return jsonify({'results': []})

    workers = min(10, len(items))
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
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)