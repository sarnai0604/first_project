from flask import Flask, request, jsonify, render_template_string
from curl_cffi import requests as cf_requests
from concurrent.futures import ThreadPoolExecutor
import re, time, itertools, threading

app = Flask(__name__)

COOKIES = [
    'datr=hqKFaDtm82hAyDfuetyPIalb; sb=hqKFaCbuioK4kXA8wTjsfZFf; ps_l=1; ps_n=1; c_user=61590423134185; oo=v1%7C3%3A1781506156; xs=22%3A-JQwJ5Vtdr2Uzg%3A2%3A1781506154%3A-1%3A-1%3A%3AAcwXoqeov6llrq9RMRR9NGWGvpcff93CSy7YxELM7A; wd=150x739; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781506162009%2C%22v%22%3A1%7D',
    'datr=hqKFaDtm82hAyDfuetyPIalb; sb=hqKFaCbuioK4kXA8wTjsfZFf; ps_l=1; ps_n=1; oo=v1; c_user=61590727440595; xs=29%3AX0EwSnbQOCaKsA%3A2%3A1781505977%3A-1%3A-1%3A%3AAczjaZ740af9uXEmJwO_LxCvrTPmd_ex9kxQqueQBw; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781505982641%2C%22v%22%3A1%7D; wd=150x739; fr=1mmcC2R87b3qrazNe.AWc5G0-IOSvbbncABQLDY5zFjrO1O-EyYFM766cFCQXN5Bcde-0.BqL5-8..AAA.0.0.BqL5_F.AWcgmXLyNM2KbBr4Ooia40Xi_18',
    'datr=0f4TaniQolJ5C4YoG81CwSqZ; ps_l=1; ps_n=1; c_user=100021418158790; xs=23%3AwFJABj_vU7RCKw%3A2%3A1779695328%3A-1%3A-1%3A%3AAcy9GiVlisEoz9oluJq_cPViIpp3m57DIABrmF_GP94; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1781233195055%2C%22v%22%3A1%7D; wd=150x828; fr=1ySmBbI4Yg99LH2FS.AWf196ghAANvuHHNqEa17HldXXxgJzHzBQI2PwWFgwTA6WcmSK8.BqK3S3..AAA.0.0.BqK3YR.AWcaUMtM8qq4wCETmNWE_blMXVc',
    ]

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
_cycle = itertools.cycle(COOKIES)
_lock  = threading.Lock()

def get_headers():
    with _lock:
        cookie = next(_cycle)
    return {'User-Agent': USER_AGENT, 'Cookie': cookie}

HTML = '''<!DOCTYPE html>
<html lang="mn">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FB ID Lookup</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #f0f2f5; min-height: 100vh; display: flex; justify-content: center; padding: 30px 16px; }
  .card { background: white; border-radius: 16px; padding: 32px; width: 100%; max-width: 1100px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); text-align: center; height: fit-content; }
  .logo { color: #1877f2; font-size: 26px; font-weight: bold; margin-bottom: 6px; }
  .sub { color: #888; margin-bottom: 20px; font-size: 13px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; }
  .tab { flex: 1; padding: 10px; border: 2px solid #e0e0e0; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; background: white; color: #888; }
  .tab.active { border-color: #1877f2; color: #1877f2; background: #f0f6ff; }
  input { width: 100%; padding: 12px 16px; border: 2px solid #e0e0e0; border-radius: 10px; font-size: 15px; outline: none; }
  input:focus { border-color: #1877f2; }
  textarea { width: 100%; padding: 12px 16px; border: 2px solid #e0e0e0; border-radius: 10px; font-size: 13px; outline: none; resize: vertical; min-height: 120px; font-family: monospace; }
  textarea:focus { border-color: #1877f2; }
  button { width: 100%; margin-top: 10px; padding: 13px; background: #1877f2; color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; }
  button:hover { background: #1565c0; }
  button:disabled { background: #b0c4e8; cursor: not-allowed; }
  .result-box { margin-top: 16px; padding: 14px; border-radius: 10px; font-size: 20px; font-weight: bold; display: none; }
  .result-box.success { background: #e8f5e9; color: #2e7d32; }
  .result-box.error { background: #ffebee; color: #c62828; }
  .bulk-results { margin-top: 16px; text-align: left; display: none; overflow-x: auto; }
  .bulk-results table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .bulk-results th { background: #f0f2f5; padding: 8px 12px; text-align: left; vertical-align: middle; }
  .col-copy { display: inline-block; margin-left: 6px; font-size: 10px; color: #1877f2; cursor: pointer; font-weight: 400; border: 1px solid #1877f2; border-radius: 4px; padding: 1px 5px; user-select: none; }
  .col-copy:hover { background: #e8f0fe; }
  .num { color: #555; font-size: 12px; }
  .bulk-results td { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }
  .bulk-results tr:hover td { background: #f9f9f9; cursor: pointer; }
  .found { color: #2e7d32; font-weight: 600; }
  .notfound { color: #aaa; }
  .deleted { color: #e53935; font-size: 11px; }
  .deleted { color: #e65100; font-weight: 600; }
  .progress { margin-top: 10px; font-size: 13px; color: #888; display: none; }
  .copy-all { margin-top: 8px; padding: 8px; background: #f0f6ff; color: #1877f2; border: 1px solid #1877f2; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; width: 100%; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">FB ID server</div>
  <div class="sub">Username → ID · ID → Username</div>
  <div class="tabs">
    <button class="tab active" onclick="switchTab(this,'single')">Нэг хайлт</button>
    <button class="tab" onclick="switchTab(this,'bulk')">Олон хайлт (200)</button>
  </div>
  <div id="single-panel">
    <input id="inp" placeholder="Username эсвэл тоон ID..." autofocus />
    <button id="btn" onclick="searchSingle()">Хайх</button>
    <div class="result-box" id="result"></div>
  </div>
  <div id="bulk-panel" style="display:none">
    <textarea id="bulk-inp" placeholder="Нэг мөрт нэг утга&#10;e.sarangua.350041&#10;100030016260618&#10;..."></textarea>
    <button id="bulk-btn" onclick="searchBulk()">Хайх</button>
    <div class="progress" id="progress"></div>
    <div class="bulk-results" id="bulk-results">
      <button class="copy-all" onclick="copyAll(this)">Бүх үр дүнг хуулах</button>
      <table><thead><tr>
        <th>Оруулсан</th>
        <th>Үр дүн <span class="col-copy" onclick="copyCol('r',this)">copy</span></th>
        <th>Friends <span class="col-copy" onclick="copyCol('friends',this)">copy</span></th>
        <th>Followers <span class="col-copy" onclick="copyCol('followers',this)">copy</span></th>
        <th>Following <span class="col-copy" onclick="copyCol('following',this)">copy</span></th>
        <th>Closed <span class="col-copy" onclick="copyCol('is_closed',this)">copy</span></th>
        <th>Gender <span class="col-copy" onclick="copyCol('gender',this)">copy</span></th>
        <th>ID Deleted <span class="col-copy" onclick="copyCol('is_deleted',this)">copy</span></th>
      </tr></thead>
      <tbody id="bulk-tbody"></tbody></table>
    </div>
  </div>
</div>
<script>
  document.getElementById('inp').addEventListener('keydown', function(e){ if(e.key==='Enter') searchSingle(); });

  function switchTab(el, tab) {
    document.querySelectorAll('.tab').forEach(function(t){ t.classList.remove('active'); });
    el.classList.add('active');
    document.getElementById('single-panel').style.display = tab === 'single' ? 'block' : 'none';
    document.getElementById('bulk-panel').style.display = tab === 'bulk' ? 'block' : 'none';
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text);
      return;
    }
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:0;left:0;width:2px;height:2px;opacity:0.01;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, 99999);
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  function showCopyModal(text) {
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center;';
    var box = document.createElement('div');
    box.style.cssText = 'background:white;padding:20px;border-radius:12px;width:92%;max-width:500px;';
    box.innerHTML = '<div style="font-weight:600;margin-bottom:8px;font-size:14px;">Cmd+A → Cmd+C дарж хуулна уу</div>';
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'width:100%;height:180px;font-size:12px;font-family:monospace;border:1px solid #ddd;border-radius:6px;padding:8px;';
    box.appendChild(ta);
    var closeBtn = document.createElement('button');
    closeBtn.textContent = 'Хаах';
    closeBtn.style.cssText = 'margin-top:8px;width:100%;padding:10px;background:#1877f2;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600;';
    closeBtn.onclick = function() { document.body.removeChild(overlay); };
    box.appendChild(closeBtn);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, 99999);
    try { document.execCommand('copy'); } catch(e) {}
  }

  function searchSingle() {
    var val = document.getElementById('inp').value.trim();
    if (!val) return;
    var btn = document.getElementById('btn');
    btn.disabled = true; btn.textContent = 'Хайж байна...';
    document.getElementById('result').style.display = 'none';
    fetch('/lookup?q=' + encodeURIComponent(val))
      .then(r => r.json())
      .then(data => {
        var box = document.getElementById('result');
        box.style.display = 'block';
        if (data.result === '-') {
          box.className = 'result-box error';
          box.textContent = '- (username байхгүй)';
        } else if (data.result && data.result !== '0') {
          box.className = 'result-box success';
          var extra = '';
          if (data.friends) extra += ' | ' + data.friends + ' friends';
          if (data.followers) extra += ' | ' + data.followers + ' followers';
          if (data.following) extra += ' | ' + data.following + ' following';
          if (data.is_closed) extra += ' | ' + data.is_closed;
          box.textContent = data.result + extra;
          copyText(data.result);
        } else {
          box.className = 'result-box error';
          box.textContent = '0 (хайж чадаагүй)';
        }
        btn.disabled = false; btn.textContent = 'Хайх';
      });
  }

  var bulkResults = [];

  async function searchBulk() {
    var lines = document
      .getElementById('bulk-inp')
      .value
      .split(/\\r?\\n/)
      .map(s => s.trim())
      .filter(Boolean);
    if (!lines.length) return;
    if (lines.length > 200) { alert('Хамгийн ихдээ 200 мөр!'); return; }
    var btn = document.getElementById('bulk-btn');
    btn.disabled = true;
    bulkResults = [];
    document.getElementById('bulk-tbody').innerHTML = '';
    document.getElementById('bulk-results').style.display = 'block';
    var prog = document.getElementById('progress');
    prog.style.display = 'block';
    prog.textContent = lines.length + ' хайлт илгээж байна...';
    try {
      var resp = await fetch('/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({items: lines})
      });
      var data = await resp.json();
      var results = data.results;
      var tbody = document.getElementById('bulk-tbody');
      for (var i = 0; i < lines.length; i++) {
        var q = lines[i];
        var item = results[i] || {r: '0', friends: '', followers: '', following: '', is_closed: '', gender: '', is_deleted: ''};
        var r = item.r || '0';
        var friends = item.friends || '';
        var followers = item.followers || '';
        var following = item.following || '';
        var is_closed = item.is_closed || '';
        var gender = item.gender || '';
        var is_deleted = item.is_deleted || '';
        bulkResults.push({q: q, r: r, friends: friends, followers: followers, following: following, is_closed: is_closed, gender: gender, is_deleted: is_deleted});
        var tr = document.createElement('tr');
        var cls = r && r !== '0' && r !== '-' ? 'found' : (r === '-' ? 'deleted' : 'notfound');
        var isFound = cls === 'found';
        tr.innerHTML = '<td>' + q + '</td>'
          + '<td class="' + cls + '">' + r + '</td>'
          + '<td class="num">' + friends + '</td>'
          + '<td class="num">' + followers + '</td>'
          + '<td class="num">' + following + '</td>'
          + '<td class="num">' + is_closed + '</td>'
          + '<td class="num">' + gender + '</td>'
          + '<td class="num">' + is_deleted + '</td>'
;
        tr.addEventListener('click', function(res, found){ return function(){
          if (!found) return;
          copyText(res);
          this.style.background = '#c8e6c9';
          setTimeout(function(el){ el.style.background = ''; }.bind(null, this), 600);
        }; }(r, isFound));
        tbody.appendChild(tr);
      }
      prog.textContent = 'Дууслаа! ' + lines.length + ' хайлт хийлээ.';
    } catch(e) {
      prog.textContent = 'Алдаа гарлаа.';
    }
    btn.disabled = false;
  }

  function copyCol(field, el) {
    var text = bulkResults.map(function(x){ return x[field] || ''; }).join('\\n');
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:0;left:0;width:2px;height:2px;';
    document.body.appendChild(ta);
    ta.focus(); ta.select(); ta.setSelectionRange(0, 99999);
    document.execCommand('copy');
    document.body.removeChild(ta);
    el.textContent = 'paste';
    setTimeout(function(){ el.textContent = 'copy'; }, 1500);
  }

  function copyAll(btn) {
    var text = bulkResults.map(function(x){ return x.r + '\\t' + x.friends + '\\t' + x.followers + '\\t' + x.following + '\\t' + x.is_closed + '\\t' + x.gender + '\\t' + x.is_deleted; }).join('\\n');
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:0;left:0;width:2px;height:2px;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, 99999);
    document.execCommand('copy');
    document.body.removeChild(ta);
    var orig = btn.textContent;
    btn.textContent = 'Хуулагдлаа!';
    setTimeout(function(){ btn.textContent = orig; }, 1500);
  }
</script>
</body>
</html>'''

@app.route('/')
def index():
    return render_template_string(HTML)

_GONE_PATTERNS = [
    "This content isn't available",
    "Sorry, this content isn't available",
    "This page isn't available",
    "The link you followed may be broken",
    "content_not_found",
    "PageNotFound",
    '"isNotAvailable":true',
    '"__typename":"CometErrorRoot"',
]

def _is_gone(resp):
    if resp.status_code == 404:
        return True
    url = resp.url
    if '/home.php' in url or url.rstrip('/').endswith('facebook.com'):
        return True
    return any(p in resp.text for p in _GONE_PATTERNS)

def _get_counts(text):
    m = (re.search(r'"text":"([\d.,KkMm]+)\s*followers?"', text) or
         re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*followers?', text, re.IGNORECASE) or
         re.search(r'>([\d.,KkMm]+)</strong>\s*followers?', text, re.IGNORECASE) or
         re.search(r'>([\d.,KkMm]+)\s*followers?', text, re.IGNORECASE))
    followers = m.group(1).strip() if m else ''

    m = (re.search(r'"text":"([\d.,KkMm]+)\s*following"', text) or
         re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*following', text, re.IGNORECASE) or
         re.search(r'>([\d.,KkMm]+)</strong>\s*following', text, re.IGNORECASE) or
         re.search(r'>([\d.,KkMm]+)\s*following', text, re.IGNORECASE))
    following = m.group(1).strip() if m else ''

    m = (re.search(r'"text":"([\d.,KkMm]+)\s*friends?"', text) or
         re.search(r'([\d.,KkMm]+)\s*<\/strong>\s*(?:friends?|найз)', text, re.IGNORECASE) or
         re.search(r'([\d.,KkMm]+)\s*(?:friends?|найз)', text, re.IGNORECASE))
    friends = ''
    if m:
        val = m.group(1).strip()
        clean = val.replace('.', '').replace(',', '')
        if clean and any(c.isalnum() for c in clean):
            friends = val

    return followers, following, friends

def _get_friends_mobile(q):
    """mbasic.facebook.com — JS байхгүй, хамгийн энгийн HTML, friends count шууд текстэд байдаг."""
    try:
        h = get_headers()
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cookie': h['Cookie'],
        }
        resp = cf_requests.get(
            f'https://mbasic.facebook.com/{q}',
            headers=headers,
            impersonate='chrome120',
            timeout=15,
            allow_redirects=True
        )
        if 'login' in resp.url or 'checkpoint' in resp.url:
            return ''
        text = resp.text
        m = re.search(r'"friend_count"\s*:\s*(\d+)', text)
        if m:
            return m.group(1)
        m = re.search(r'([\d.,KkMm]+)\s*</strong>\s*(?:friends?|найз)', text, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r'([\d.,KkMm]+)\s*(?:friends?|найз)', text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            clean = val.replace('.', '').replace(',', '')
            if clean and any(c.isalnum() for c in clean):
                return val
        return ''
    except Exception:
        return ''

def _is_deactivated(text):
    # "isAdminViewingDeactivatedProfile":null → active
    # "isAdminViewingDeactivatedProfile":true  → deactivated
    m = re.search(r'"isAdminViewingDeactivatedProfile"\s*:\s*(\w+)', text)
    if m and m.group(1) != 'null':
        return True
    return False

def _is_closed(text):
    if ('"LockedProfileTryItBanner"' in text
            or 'locked her profile' in text
            or 'locked his profile' in text
            or 'locked their profile' in text):
        return 'locked'
    return 'open'

def _get_gender(text):
    m = re.search(r'[,{]"gender"\s*:\s*"([^"]+)"', text)
    if not m:
        m = re.search(r'"gender"\s*:\s*"([^"]+)"', text)
    if m:
        g = m.group(1).upper()
        if g == 'FEMALE':
            return 'Female'
        if g == 'MALE':
            return 'Male'
        if g == 'NEUTER':
            return 'Unknown'
        return 'Unknown'
    return ''


def _empty():
    return {'r': '0', 'followers': '', 'following': '', 'friends': '', 'is_closed': '', 'gender': '', 'is_deleted': ''}

def _deleted():
    return {'r': '-', 'followers': '', 'following': '', 'friends': '', 'is_closed': '', 'gender': '', 'is_deleted': '-'}

def _lookup_once(q):
    try:
        if q.isdigit():
            resp = cf_requests.get(
                f'https://www.facebook.com/{q}',
                headers=get_headers(),
                impersonate='chrome120',
                timeout=15,
                allow_redirects=True
            )
            if 'login' in resp.url or 'checkpoint' in resp.url:
                return _empty()
            if _is_gone(resp):
                return _deleted()
            if _is_deactivated(resp.text):
                return _deleted()
            final_url = resp.url.rstrip('/').split('?')[0].split('#')[0]
            slug = final_url.split('facebook.com/')[-1].strip('/')
            if slug.startswith('people'):
                return {'r': '-', 'followers': '', 'following': '', 'friends': '', 'is_closed': '', 'gender': '', 'is_deleted': ''}
            followers, following, friends = _get_counts(resp.text)
            closed = _is_closed(resp.text)
            gender = _get_gender(resp.text)
            if (slug and slug != q and not slug.isdigit()
                    and not slug.startswith('profile')
                    and not slug.startswith('login')
                    and not slug.startswith('home')
                    and re.match(r'^[\w.-]+$', slug)):
                if not friends:
                    friends = _get_friends_mobile(slug)
                return {'r': slug, 'followers': followers, 'following': following, 'friends': friends, 'is_closed': closed, 'gender': gender, 'is_deleted': ''}
            m = re.search(r'"userVanity":"([^"]+)","userID":"' + q + '"', resp.text)
            if not m:
                m = re.search(r'"userID":"' + q + r'","userVanity":"([^"]+)"', resp.text)
            if m and not m.group(1).isdigit():
                uname = m.group(1)
                if not friends:
                    friends = _get_friends_mobile(uname)
                return {'r': uname, 'followers': followers, 'following': following, 'friends': friends, 'is_closed': closed, 'gender': gender, 'is_deleted': ''}
            m = re.search(r'"url":"https:\\/\\/www\.facebook\.com\\/([^"\\/]+)"', resp.text)
            if m:
                val = m.group(1)
                if (not val.isdigit() and not val.startswith('profile')
                        and re.match(r'^[\w.-]+$', val)):
                    if not friends:
                        friends = _get_friends_mobile(val)
                    return {'r': val, 'followers': followers, 'following': following, 'friends': friends, 'is_closed': closed, 'gender': gender, 'is_deleted': ''}
            if not friends:
                friends = _get_friends_mobile(q)
            return _empty()
        else:
            resp = cf_requests.get(
                f'https://www.facebook.com/{q}',
                headers=get_headers(),
                impersonate='chrome120',
                timeout=25
            )
            if 'login' in resp.url or 'checkpoint' in resp.url:
                return _empty()
            if _is_gone(resp):
                return _deleted()
            if _is_deactivated(resp.text):
                return _deleted()
            followers, following, friends = _get_counts(resp.text)
            closed = _is_closed(resp.text)
            gender = _get_gender(resp.text)
            if not friends:
                friends = _get_friends_mobile(q)
            m = re.search(r'"userVanity":"[^"]+","userID":"(\d+)"', resp.text)
            if not m:
                m = re.search(r'"userID":"(\d{8,})"', resp.text)
            uid = m.group(1) if m else '0'
            return {'r': uid, 'followers': followers, 'following': following, 'friends': friends, 'is_closed': closed, 'gender': gender, 'is_deleted': ''}
    except Exception:
        return _empty()

def do_lookup(q):
    result = _lookup_once(q)
    if result['r'] == '0':
        time.sleep(1)
        result = _lookup_once(q)
    return result




    

@app.route('/batch', methods=['POST'])
def batch():
    data = request.get_json(silent=True) or {}
    items = [str(x).strip() for x in data.get('items', []) if str(x).strip()]
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(do_lookup, items))
    return jsonify({'results': results})

@app.route('/lookup')
def lookup():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'result': ''})
    d = do_lookup(q)
    return jsonify({'result': d['r'], 'friends': d['friends'], 'followers': d['followers'], 'following': d['following'], 'is_closed': d['is_closed'], 'gender': d['gender'], 'is_deleted': d['is_deleted']})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9090, debug=False, threaded=True)