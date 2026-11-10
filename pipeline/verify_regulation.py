#!/usr/bin/env python3
"""Check every pharmacy we list against the GPhC register of pharmacy premises.

Per provider, in order of strength:
  1. a GPhC number the pharmacy publishes on its own site -> look the number up
  2. a search of the register by trading name
Each result records what was found, so the verdict can be argued with.

Verdicts
  verified_number  the published number resolves to a registered premises
  verified_name    a registered premises trades under this brand
  partner          the number belongs to a different trading name (white-label)
  unverified       nothing on the register matched

Writes reports/regulation-audit.json. Throttled: the register blocks heavy use.
"""
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
BASE = "https://www.pharmacyregulation.org/registers/pharmacy"
DELAY = 1.3

STOP = {"pharmacy", "online", "chemist", "the", "uk", "clinic", "health", "ltd", "limited"}

jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
op.addheaders = [("User-Agent", UA), ("Accept", "text/html,application/xhtml+xml")]


def tokens():
    h = op.open(BASE, timeout=30).read().decode("utf-8", "replace")
    bid = re.search(r'name="form_build_id"[^>]*value="([^"]+)"', h)
    fid = re.search(r'name="form_id"[^>]*value="([^"]+)"', h)
    return (bid.group(1) if bid else "", fid.group(1) if fid else "register_search_pharmacy_form")


def query(kind, value):
    """kind: 'name' or 'regno'."""
    bid, fid = tokens()
    form = {"type": "name", "name": "", "address": "", "regno": "", "owner_name": "",
            "unsure_spelling": "0", "form_build_id": bid, "form_id": fid, "op": "Search"}
    if kind == "name":
        form["name"] = value
    else:
        form["type"] = "registration_number"
        form["regno"] = value
    page = op.open(BASE, urllib.parse.urlencode(form).encode(), timeout=30).read().decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
        if len(cells) >= 5:
            rows.append({"name": cells[0].replace(" See registration details", "").strip(),
                         "owner": cells[1], "address": cells[2],
                         "regno": cells[3], "status": cells[4]})
    total = re.search(r"Displaying results [\d,]+ to [\d,]+ of ([\d,]+)", page)
    return rows, (int(total.group(1).replace(",", "")) if total else len(rows))


def brand_tokens(name):
    words = re.findall(r"[a-z]+", name.lower())
    return [w for w in words if w not in STOP and len(w) > 2]


def verdict_for(provider, number):
    toks = brand_tokens(provider)
    out = {"provider": provider, "number_on_site": number}

    if number:
        rows, _ = query("regno", number)
        time.sleep(DELAY)
        live = [r for r in rows if r["status"].lower().startswith("reg")]
        if live:
            r = live[0]
            same = any(t in r["name"].lower() for t in toks) if toks else False
            out.update(verdict="verified_number" if same else "partner",
                       registered_name=r["name"], owner=r["owner"],
                       address=r["address"], regno=r["regno"], status=r["status"])
            return out

    rows, total = query("name", provider)
    time.sleep(DELAY)
    hits = [r for r in rows if any(t in r["name"].lower() for t in toks)] if toks else []
    live = [r for r in hits if r["status"].lower().startswith("reg")]
    if live:
        r = live[0]
        out.update(verdict="verified_name", registered_name=r["name"], owner=r["owner"],
                   address=r["address"], regno=r["regno"], status=r["status"],
                   name_matches=len(live), total_results=total)
        return out

    out.update(verdict="unverified", total_results=total,
               nearest=[r["name"] for r in rows[:3]])
    return out


def main():
    index = json.loads((ROOT / "www/data/price-index.json").read_text())["providers"]
    gphc = json.loads((ROOT / "www/data/gphc.json").read_text())["providers"]
    ordering = json.loads((ROOT / "www/data/ordering.json").read_text())["providers"]

    names = sorted({p["provider"] for p in index} | {
        n for n, v in ordering.items() if isinstance(v, dict) and v.get("steps")}
        | set(gphc.keys()))

    results = {}
    for i, name in enumerate(names, 1):
        number = (gphc.get(name) or {}).get("number")
        try:
            results[name] = verdict_for(name, number)
        except Exception as exc:  # keep going; one failure must not stop the audit
            results[name] = {"provider": name, "verdict": "error", "error": str(exc)[:120]}
            time.sleep(DELAY * 3)
        print(f"[{i}/{len(names)}] {name}: {results[name]['verdict']}", flush=True)
        time.sleep(DELAY)

    out = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
           "source": "pharmacyregulation.org register of pharmacy premises",
           "providers": results}
    (ROOT / "reports/regulation-audit.json").write_text(json.dumps(out, indent=1))
    counts = {}
    for v in results.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    print("\n" + json.dumps(counts, indent=1), flush=True)


if __name__ == "__main__":
    main()
