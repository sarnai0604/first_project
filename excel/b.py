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
    'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100021418158790; xs=38%3ABiHnEBeMmB0_QA%3A2%3A1782359706%3A-1%3A-1%3A%3AAcwXj0JI1_D8bD1gxQC71XroU9EMTnlgqBekFgqXlw; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781682787314%2C%22v%22%3A1%7D; wd=363x794; fr=1qAlNUwIFcukl1o7c.AWeUvFUaOALcq73o5k4nph-PrYlIBdORwcsiJLd_xNf63R01sw0.BqPKaf..AAA.0.0.BqPKaf.AWc2rx0YU_4lilKc1mPrnDr_ER4;',
    # 'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100090316622127; xs=29%3AZzWPlMggEDCuQg%3A2%3A1782359197%3A-1%3A-1%3A%3AAcyGZZyZiVi_LqTlKW9iAblBn2kyBcumbe90bZv-gQ; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781749955177%2C%22v%22%3A1%7D; wd=363x794; fr=1GMOCPoTpv57x7dkH.AWcyB_2lW7bLCOcaEHYqNEKek3_RRulDyazk_sZZEANZiTdtoMg.BqPKS1..AAA.0.0.BqPKS1.AWfiWmsCrfCwrO3r12erZ-Zv6mA;'
]



USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

_cycle = itertools.cycle(COOKIES)
_cookie_lock = threading.Lock()

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
        num *= 1000
    elif suffix == 'M':
        num *= 1000000
    return str(int(num))

def _extract_location(html):
    m = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"(?:Lives in|From)\s+([^"]+)"', html)
    if m:
        return m.group(1).strip()
    m = re.search(r'"text"\s*:\s*"(?:Lives in|From)\s+([^"]+)"', html)
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
    return bool(m and m.group(1) == 'true')

def do_lookup(q):
    session = get_session()
    empty_res   = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": "", "is_closed": "", "is_deleted": "", "location": ""}
    deleted_res = {"username": "", "id": "", "friends": "", "followers": "", "following": "", "gender": "", "is_closed": "", "is_deleted": "-", "location": ""}

    try:
        time.sleep(random.uniform(0.3, 1.0))
        headers = get_headers()

        if q.isdigit():
            resp = session.get(
                f'https://www.facebook.com/{q}',
                headers=headers,
                timeout=20,
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

        friends = followers = following = ''

        profile_valid = bool(fb_id)

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

        # Gender
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
                elif raw == 'unknown':
                    gender = 'unknown'

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
        print("LOOKUP ERROR:", e)
        return empty_res
    finally:
        release_session(session)

@app.route('/')
def index():
    return send_from_directory('static', 'index1.html')

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
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)