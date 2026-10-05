from concurrent.futures import ThreadPoolExecutor
from html import unescape
import json
import os
import re
from curl_cffi import requests as cf_requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

COOKIE = (
    "datr=dkWzaoRYBdX5iFYb4vTFwTyQ; "
    "sb=dkWzaqnjcK-8e9lWChGv2Kml; "
    "c_user=61563290321218; "
    "xs=45%3AJ0GTrVS14uxGKw%3A2%3A1790133662%3A-1%3A-1%3A%3AAcx-CDqnku9qAftxTI8QdFloNvhTyJRmhxVb2kn-Cw; "
    "fr=1CLDcRnXuo4QwTpvV.AWcrv3jUwlBkVgCtmZm6iWi73lpYMrs8e4I4whl-nsXNB14OW2s.Bqs0Wj..AAA.0.0.Bqs0Wj.AWcgoDEctBSrAbG5Lck7TjD_hSY"
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
            value = float(num.replace(",", ".")) * multipliers[suffix.lower()]
        else:
            value = float(num.replace(",", "").replace(".", ""))
        return int(round(value))
    except ValueError:
        return s


# ── Location extract ────────────────────────────────────────
def _extract_locations(html):
    lives_in = ""
    from_place = ""

    m_lives = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if not m_lives:
        m_lives = re.search(r'"text"\s*:\s*"Lives in\s+([^"]+)"', html)
    if m_lives:
        raw_lives = m_lives.group(1)
        try:
            fixed_lives = json.loads(f'"{raw_lives}"')
            lives_in = _decode_text(fixed_lives)
        except Exception:
            lives_in = _decode_text(raw_lives)

    m_from = re.search(r'"text"\s*:\s*\{\s*"text"\s*:\s*"From\s+([^"]+)"', html)
    if not m_from:
        m_from = re.search(r'"text"\s*:\s*"From\s+([^"]+)"', html)
    if m_from:
        raw_from = m_from.group(1)
        try:
            fixed_from = json.loads(f'"{raw_from}"')
            from_place = _decode_text(fixed_from)
        except Exception:
            from_place = _decode_text(raw_from)

    # location гэдэгт lives_in эсвэл from_place-ийг нэгтгэж буцаах
    if lives_in and from_place:
        return f"{lives_in} (From: {from_place})"
    return lives_in or from_place or ""


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
def do_lookup(q):
    empty_res = {
        "username": "",
        "id": "",
        "friends": "",
        "followers": "",
        "following": "",
        "gender": "",
        "is_closed": "",
        "is_deleted": "",
        "location": "",
    }

    if not q.isdigit():
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

        # Устсан эсвэл хандах боломжгүй эсэхийг шалгах хэсэг
        if (
            resp.status_code == 404 
            or "checkpoint" in resp.url 
            or "This content isn't available right now" in resp.text
        ):
            empty_res["is_deleted"] = "true"  # Устсан эсвэл байхгүй бол true болгоно
            return empty_res

        if "login" in resp.url:
            empty_res["is_deleted"] = "true"
            return empty_res

        final_url = resp.url.rstrip("/").split("?")[0].split("#")[0]
        slug = final_url.split("facebook.com/")[-1].strip("/")
        if not (
            slug and slug != q and not slug.isdigit() and re.match(r"^[\w.]+$", slug)
        ):
            slug = ""
        fb_id = q

        html_content = resp.text

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

        location = _extract_locations(html_content)

        return {
            "username": slug,
            "id": fb_id,
            "friends": friends,
            "followers": followers,
            "following": following,
            "gender": gender,
            "is_closed": is_closed,
            "is_deleted": "",
            "location": location,
        }

    except Exception as e:
        print("LOOKUP ERROR:", e)
        empty_res["is_deleted"] = "true"
        return empty_res
    finally:
        session.close()


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index2.html")


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