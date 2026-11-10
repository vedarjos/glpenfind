#!/usr/bin/env python3
"""Say why each remaining pharmacy is unread: gated, blocked, or no price found."""
import html, json, re, ssl, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
FWD = re.compile(r"(2\.5|5|7\.5|10|12\.5|15)\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
GATE = re.compile(r"(complete (our|the|your) (online )?(consultation|assessment|questionnaire)|"
                  r"start (your|the) (online )?(consultation|assessment)|"
                  r"(price|pricing)s? (is |are )?(shown|revealed|displayed) (after|once)|"
                  r"answer (a few|some) questions|before (we can )?(show|display) (you )?(a )?price|"
                  r"sign in to (see|view) price|log ?in to (see|view) price)", re.I)
PATHS = ["", "/mounjaro", "/treatments/mounjaro", "/weight-loss/mounjaro", "/mounjaro-weight-loss",
         "/online-doctor/mounjaro", "/services/weight-loss"]


def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return r.status, r.read(1_200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)[:40]


def text_of(b):
    b = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", b)))


def check(entry):
    name, domain = entry["provider"], entry.get("domain", "")
    out = {"provider": name, "domain": domain, "status": None, "prices": 0, "gate": False, "note": ""}
    home_status, home_body = get(f"https://{domain}/")
    out["home_status"] = home_status
    if home_status != 200 or not home_body:
        out["status"] = home_status
        out["note"] = "home page did not load"
        return out
    for path in PATHS:
        status, body = get(f"https://{domain}{path}")
        if not body:
            continue   # a guessed path 404ing is not a block
        out["status"] = status
        if not body:
            continue
        t = text_of(body)
        out["status"] = out["status"] or status
        if GATE.search(t):
            out["gate"] = True
            m = GATE.search(t)
            out["note"] = m.group(0)[:70]
        found = {m.group(1) for m in FWD.finditer(t)}
        out["prices"] = max(out["prices"], len(found))
        if out["prices"] >= 3:
            return out
    return out


def main():
    idx = json.loads((APP / "price-index.json").read_text())
    todo = [u for u in idx["unread"] if u.get("domain")]
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(check, todo))
    Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/reports/why-unread.json").write_text(json.dumps(rows, indent=1))
    for r in rows:
        verdict = ("gated: " + r["note"]) if r["gate"] else (
            f"blocked (home page {r.get('home_status')})" if (r.get("home_status") or 0) != 200 else "no price found")
        print(f"{r['provider']:<24} {verdict}")


if __name__ == "__main__":
    main()
