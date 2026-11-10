#!/usr/bin/env python3
"""Second attempt at the 56 pharmacies we recorded as unpriced.

The first crawl only followed homepage links whose href contained "mounjaro" and
gave up when a product page sat behind a menu, a redirect or a JS-rendered card.
This pass tries a set of likely product paths directly and records anything that
yields a dose/price pair.

Outputs reports/unread-retry.json and appends recoveries to the crawl journal.
"""
from __future__ import annotations

import html
import json
import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
REPORT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/reports/unread-retry.json")
JRNL = Path("/Users/PetroulaKostofska/.hermes/cache/scratch/crawl_raw.jsonl")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
FWD = re.compile(r"(2\.5|5|7\.5|10|12\.5|15)\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
REV = re.compile(r"\u00a3\s?(\d{2,3}(?:\.\d{2})?)[^\u00a3]{0,110}?(2\.5|5|7\.5|10|12\.5|15)\s?mg", re.I)

PATHS = [
    "/mounjaro", "/mounjaro/", "/mounjaro.html", "/weight-loss/mounjaro", "/weight-loss/mounjaro/",
    "/mounjaro-weight-loss", "/treatments/mounjaro", "/online-doctor/mounjaro",
    "/weight-management/mounjaro", "/product/mounjaro", "/products/mounjaro",
    "/weight-loss/mounjaro-injection", "/mounjaro-injection", "/prescriptions/mounjaro",
    "/collections/mounjaro", "/shop/mounjaro",
]


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-GB,en"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return r.status, r.read(1_500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def text_of(body: str) -> str:
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))


def pairs(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for m in FWD.finditer(text):
        found.setdefault(m.group(1), float(m.group(2)))
    for m in REV.finditer(text):
        found.setdefault(m.group(2), float(m.group(1)))
    return {d: p for d, p in found.items() if 80 <= p <= 400}


def try_domain(entry: dict) -> dict:
    name, domain = entry["provider"], entry.get("domain") or ""
    if not domain:
        return {"provider": name, "domain": "", "recovered": False, "reason": "no domain"}
    best = {"provider": name, "domain": domain, "recovered": False, "prices": {}, "url": ""}
    for path in PATHS:
        url = f"https://{domain}{path}"
        status, body = fetch(url)
        if status != 200 or not body:
            continue
        found = pairs(text_of(body))
        if len(found) > len(best["prices"]):
            best.update({"prices": found, "url": url, "status": status})
        if len(found) >= 5:
            break
    best["recovered"] = len(best["prices"]) >= 3
    best["doses"] = len(best["prices"])
    if not best["recovered"]:
        best["reason"] = "no product page found at the usual paths"
    return best


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    unread = [u for u in index["unread"] if u.get("domain")]
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(try_domain, unread):
            results.append(res)
            mark = "RECOVERED" if res["recovered"] else "still unseen"
            print(f"{res['provider']:<26} {mark:<12} doses={res['doses']} {res.get('url','')[:60]}", flush=True)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=1))

    recovered = [r for r in results if r["recovered"]]
    print(f"\nrecovered {len(recovered)} of {len(results)}: " + ", ".join(r["provider"] for r in recovered))

    # append recoveries to the journal so the standard pipeline picks them up
    if recovered:
        existing = {}
        if JRNL.exists():
            for line in JRNL.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    existing[row["provider"]] = row
        for r in recovered:
            existing[r["provider"]] = {
                "provider": r["provider"], "domain": r["domain"], "prices": r["prices"],
                "page": r["url"], "status": f"200/{r['doses']}",
                "note": "recovered on retry: product page found at a guessed path",
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        JRNL.write_text("\n".join(json.dumps(v) for v in existing.values()) + "\n")
        print(f"journal now holds {len(existing)} providers")


if __name__ == "__main__":
    main()
