from concurrent.futures import ThreadPoolExecutor
import os
import re
from curl_cffi import requests as cf_requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

COOKIE = "datr=0f4TaniQolJ5C4YoG81CwSqZ; sb=0f4Tag_szj9t082e8Bc6butW; ps_l=1; ps_n=1; c_user=61593179188492; xs=21%3APbqAqP_18yepEA%3A2%3A1788494607%3A-1%3A-1%3A%3AAcwb8zMasYrdIRv9J9u7AIEMoJe2GMRaZBwKljtszEA; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1788747065991%2C%22v%22%3A1%7D"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def get_headers():
    return {"User-Agent": USER_AGENT, "Cookie": COOKIE}


def _extract_userid(html):
    patterns = [
        r'"userID"\s*:\s*"(\d+)"',
        r'"owner"\s*:\s*\{\s*"id"\s*:\s*"(\d+)"',
        r'actor_id["\']?\s*[:=]\s*["\']?(\d+)["\']?',
        r'"profile_id"\s*:\s*"(\d+)"',
        r'property="al:android:url"\s+content="fb://profile/(\d+)"',
    ]
    for p in patterns:
        m = re.search(p, html)
        if m:
            return m.group(1)
    
    m_alt = re.search(r'"entity_id"\s*:\s*"(\d+)"', html)
    if m_alt:
        return m_alt.group(1)
        
    return ""


# ── Core lookup ───────────────────────────────────────────────
def do_lookup(q):
    empty_res = {
        "query": q,
        "username": "",
        "id": ""
    }

    if not q:
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
        
        # Хэрэв slug нь profile.php эсвэл тоон утга байвал username-ийг хоосон болгох
        if not slug or "profile.php" in slug.lower() or slug.isdigit():
            slug = ""

        html_content = resp.text
        
        if q.isdigit():
            fb_id = q
        else:
            slug = q if not ("profile.php" in q.lower()) else ""
            fb_id = _extract_userid(html_content)

        return {
            "query": q,
            "username": slug,
            "id": fb_id
        }

    except Exception as e:
        print("LOOKUP ERROR:", e)
        return empty_res
    finally:
        session.close()


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index1.html")


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