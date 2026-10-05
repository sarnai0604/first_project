from concurrent.futures import ThreadPoolExecutor
from html import unescape
import json
import os
import re
from curl_cffi import requests as cf_requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

COOKIE = (
    "datr=cd2aaJ6mcbboFUomocO2pmX4; " 
    "sb=cd2aaMWO5Bqe1MxEb-EZCjJp; "
    "c_user=100021418158790; "
    "xs=26%3ANUSdrCMCWcEheg%3A2%3A1789966953%3A-1%3A-1%3A%3AAcw0iQgGX47x6celz8ASHY97DO008EG7fUrF6Qli4Fs; "
    "fr=1KYO0bzO0cU5XHjtC.AWewGox45XJJyzKbdMTT57SLuwywqzz1LwD5eEqIMdcKu71kKKs.Bqvez8..AAA.0.0.Bqvez8.AWc2PfU0M8-afwXG61M3TTflsA0"
)


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def get_headers():
    return {"User-Agent": USER_AGENT, "Cookie": COOKIE}


def _decode_text(text):
    if not text:
        return ""
    
    try:
        text = json.loads(f'"{text}"')
    except Exception:
        
        text = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1), 16)),
            text,
        )
        text = text.replace("\\/", "/").replace('\\"', '"')
        # surrogate pair (emoji г.м) зөв нийлүүлэх
        try:
            text = text.encode("utf-16", "surrogatepass").decode("utf-16")
        except Exception:
            pass
    return unescape(text).strip()


def _parse_count(s):
    """'1.2K' -> 1200, '3,5M' -> 3500000, '1,234' -> 1234"""
    if not s:
        return ""
    s = s.strip().replace(" ", "")
    m = re.fullmatch(r"([\d.,]+)([KkMmBb]?)", s)
    if not m:
        return s

    num, suffix = m.groups()
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}

    try:
        if suffix:
            # 1,2K гэсэн бичлэгийг 1.2K гэж үзнэ
            value = float(num.replace(",", ".")) * multipliers[suffix.lower()]
        else:
            # 1,234 эсвэл 1.234 гэсэн мянгатын таслалыг арилгана
            value = float(num.replace(",", "").replace(".", ""))
        return int(round(value))
    except ValueError:
        return s

    

# ── Location extract (Lives in & From) ────────────────────────
def _extract_locations(html):
    lives_in = ""
    from_place = ""

    m_lives = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if not m_lives:
        m_lives = re.search(r'"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if m_lives:
        lives_in = _decode_text(m_lives.group(1))

    m_from = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"From\s+([^"]+)"', html)
    if not m_from:
        m_from = re.search(r'"text"\s*:\s*"From\s+([^"]+)"', html)
    if m_from:
        from_place = _decode_text(m_from.group(1))

    return lives_in, from_place


def _extract_category(html):
    match = re.search(r'"category_name"\s*:\s*"([^"]+)"', html)
    return _decode_text(match.group(1)) if match else ""


def _extract_displayname(html):
    m = re.search(
        r'"__isProfile"\s*:\s*"User"[^}]*?"name"\s*:\s*"((?:[^"\\]|\\.)*)"',
        html,
    )
    if m:
        return _decode_text(m.group(1))
    return ""


# ── Core lookup (ID Only) ─────────────────────────────────────
# ── Core lookup (ID & Username Support) ───────────────────────
def do_lookup(q):
    empty_res = {
        "username": "",
        "id": "",
        "display_name": "",
        "friends": "",
        "followers": "",
        "following": "",
        "gender": "",
        "is_closed": "",
        "lives_in": "",
        "from_place": "",
        "category": "",
    }

    if not q:
        return empty_res

    q = str(q).strip().rstrip("/")
    if "facebook.com/" in q:
        q = q.split("facebook.com/")[-1].split("?")[0].split("#")[0].strip("/")

    if not re.match(r"^[\w.-]+$", q):
        return empty_res

    session = cf_requests.Session(impersonate="chrome120")

    try:
        headers = get_headers()
        resp = session.get(
            f"https://www.facebook.com/{q}",
            headers=headers,
            timeout=30,
            allow_redirects=True,
        )

        if "login" in resp.url or "checkpoint" in resp.url:
            return empty_res

        final_url = resp.url.rstrip("/").split("?")[0].split("#")[0]
        slug = final_url.split("facebook.com/")[-1].strip("/")
        
        # profile.php эсвэл тоон ID байвал username-д тооцохгүй хоосон үлдээнэ
        if not (
            slug 
            and slug != q 
            and not slug.isdigit() 
            and not slug.startswith("profile.php")
            and re.match(r"^[\w.-]+$", slug)
        ):
            slug = ""

        # Хэрэв q өөрөө тоо биш бөгөөд profile.php биш бол мөн username болгон ашиглаж болно
        if not slug and not q.isdigit() and not q.startswith("profile.php"):
            slug = q

        # HTML дотроос ID олох
        m_id = re.search(r'"userID"\s*:\s*"(\d+)"', html_content := resp.text)
        if not m_id:
            m_id = re.search(r'"profile_id"\s*:\s*"(\d+)"', html_content)
        
        fb_id = m_id.group(1) if m_id else (q if q.isdigit() else "")

        friends = followers = following = ""

        # Friends
        m_friends = re.search(
            r'"text"\s*:\s*"([\d.,KkMmBb]+)\s*(?:friends|найз)"',
            html_content,
            re.IGNORECASE,
        )
        if m_friends:
            friends = _parse_count(m_friends.group(1))

        # Followers
        m_followers = re.search(
            r'"text"\s*:\s*"([\d.,KkMmBb]+)\s*(?:followers|дагагч)"',
            html_content,
            re.IGNORECASE,
        )
        if m_followers:
            followers = _parse_count(m_followers.group(1))

        # Following
        m_following = re.search(
            r'"text"\s*:\s*"([\d.,KkMmBb]+)\s*(?:following|дагаж)"',
            html_content,
            re.IGNORECASE,
        )
        if m_following:
            following = _parse_count(m_following.group(1))

        # Gender
        gender = ""
        m_gender = re.search(r'"\s*,\s*"gender"\s*:\s*"?(\w+)"?', html_content)
        if m_gender:
            raw = m_gender.group(1).lower()
            if raw in ["male", "female", "neuter", "unknown"]:
                gender = raw

        # Locked / Open
        if (
            '"LockedProfileTryItBanner"' in html_content
            or "locked her profile" in html_content
            or "locked his profile" in html_content
            or "locked their profile" in html_content
        ):
            is_closed = "locked"
        else:
            is_closed = "open"

        lives_in, from_place = _extract_locations(html_content)
        display_name = _extract_displayname(html_content)

        return {
            "username": slug,
            "id": fb_id,
            "display_name": display_name,
            "friends": friends,
            "followers": followers,
            "following": following,
            "gender": gender,
            "is_closed": is_closed,
            "lives_in": lives_in,
            "from_place": from_place,
            "category": _extract_category(html_content),
        }

    except Exception as e:
        print("LOOKUP ERROR:", e)
        return empty_res
    finally:
        session.close()


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/batch", methods=["POST"])
def batch():
    data = request.get_json(silent=True) or {}
    items = [str(x).strip() for x in data.get("items", []) if str(x).strip()]
    if not items:
        return jsonify({"results": []})

    workers = min(5, len(items))
    print(f"ITEM COUNT: {len(items)}  |  WORKERS: {workers}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(do_lookup, items))

    return jsonify({"results": results})


@app.route("/lookup")
def lookup():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"result": {}})
    return jsonify({"result": do_lookup(q)})


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)

    try:
        app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)

    except KeyboardInterrupt:
        print("\nStopping server...")