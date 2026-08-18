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
_lock  = threading.Lock()
 
def get_headers():
    with _lock:
        cookie = next(_cycle)
    return {'User-Agent': USER_AGENT, 'Cookie': cookie}
 
def do_lookup(q):
    try:
        if q.isdigit():
            resp = cf_requests.get(
                f'https://www.facebook.com/{q}',
                headers=get_headers(),
                impersonate='chrome120',
                timeout=15,
                allow_redirects=True
            )
            final_url = resp.url.rstrip('/').split('?')[0].split('#')[0]
            slug = final_url.split('facebook.com/')[-1].strip('/')
            if not (slug and slug != q and not slug.isdigit() and re.match(r'^[\w.]+$', slug)):
                slug = ''
            fb_id = q
        else:
            resp = cf_requests.get(
                f'https://www.facebook.com/{q}',
                headers=get_headers(),
                impersonate='chrome120',
                timeout=25
            )
            m = re.search(r'"userID":"(\d+)"', resp.text)
            fb_id = m.group(1) if m else ''
            slug = q
 
        html_content = resp.text
 
        friends = ''
        followers = ''
        following = ''
 
        # 1. Friends хайх (Strong & Weak Regex хоёуланг нь шалгана)
        m_friends = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:friends|найз)', html_content, re.IGNORECASE)
        if not m_friends:
            m_friends = re.search(r'([\d.,KkMm]+)\s*(?:friends|найз)', html_content, re.IGNORECASE)
       
        if m_friends:
            # Олдсон утгаас хоосон зай, цэгийг цэвэрлэж үзнэ
            clean_friends = m_friends.group(1).strip().replace('.', '').replace(',', '')
            # Хэрэв үнэхээр тоо эсвэл K, M гэсэн үсэг байвал (зүгээр нэг цэг биш бол)
            if clean_friends and any(c.isalnum() for c in clean_friends):
                friends = m_friends.group(1).strip()
 
        # 2. Шаардлага: Friends тодорхой олдоогүй бол Followers, Following-ийг заавал хайна
        if not friends:
            # Followers хайх
            m_followers = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:followers|дагагч)', html_content, re.IGNORECASE)
            if not m_followers:
                m_followers = re.search(r'([\d.,KkMm]+)\s*(?:followers|дагагч)', html_content, re.IGNORECASE)
            if m_followers:
                followers = m_followers.group(1).strip()
 
            # Following хайх
            m_following = re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:following|дагаж)', html_content, re.IGNORECASE)
            if not m_following:
                m_following = re.search(r'([\d.,KkMm]+)\s*(?:following|дагаж)', html_content, re.IGNORECASE)
            if m_following:
                following = m_following.group(1).strip()
 
        return {
            "username":  slug,
            "id":        fb_id,
            "friends":   friends,
            "followers": followers,
            "following": following
        }
 
    except Exception as e:
        print("LOOKUP ERROR:", e)
        return {"username": "", "id": "", "friends": "", "followers": "", "following": ""}
   
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')
 
@app.route('/batch', methods=['POST'])
def batch():
    data = request.get_json(silent=True) or {}
    items = [str(x).strip() for x in data.get('items', []) if str(x).strip()]
    print("ITEM COUNT:", len(items))
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(do_lookup, items))
    return jsonify({'results': results})
 
@app.route('/lookup')
def lookup():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'result': {}})
    result = do_lookup(q)
    return jsonify({'result': result})
 
if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=9090, debug=True, threaded=True)