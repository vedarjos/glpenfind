#!/usr/bin/env python3
"""Verify every provider against the GPhC pharmacy register.

Part A: providers whose registration number we already know -> GET the register
        page for that number and read name / owner / address / status.
Part B: providers with no number -> drive the register's own search form in a
        real browser, take the best name match, and record its number.

Writes www/data/gphc.json, keyed by provider name.
"""
from __future__ import annotations

import difflib
import html
import json
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
SCRATCH = Path("/Users/PetroulaKostofska/.hermes/cache/scratch")
BASE = "https://www.pharmacyregulation.org"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-GB,en"})
    with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
        return r.read(2_000_000).decode("utf-8", "replace")


def first_row(page_html: str) -> dict | None:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S)
    for row in rows:
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        cells = [c for c in cells if c]
        if len(cells) >= 5 and re.match(r"^\d{6,8}$", cells[3].replace(" ", "")):
            return {
                "name": re.sub(r"\s*See registration details$", "", cells[0]),
                "owner": cells[1],
                "address": cells[2],
                "regno": cells[3].replace(" ", ""),
                "status": cells[4],
            }
    return None


def by_number(provider: str, number: str) -> dict:
    url = f"{BASE}/registers/pharmacy/registrationnumber/{number}"
    out = {"provider": provider, "number": number, "url": url, "verified": False}
    try:
        row = first_row(fetch(url))
    except Exception as exc:
        out["error"] = str(exc)[:60]
        return out
    if not row:
        out["error"] = "no row parsed"
        return out
    match = difflib.SequenceMatcher(None, provider.lower(), row["name"].lower()).ratio()
    out.update({"registered_name": row["name"], "owner": row["owner"],
                "address": row["address"], "status": row["status"],
                "number": row["regno"], "match": round(match, 2), "method": "number",
                "verified": row["status"].lower().startswith("registered") and match >= 0.45})
    return out


def search_by_name(page, provider: str) -> dict:
    out = {"provider": provider, "number": None, "verified": False, "url": None}
    try:
        page.goto(f"{BASE}/registers/pharmacy/registrationnumber", wait_until="domcontentloaded", timeout=30000)
        page.evaluate("""(value) => {
            const input = document.querySelector('input[name="name"]');
            input.value = value;
            const form = input.form;
            const op = form.querySelector('input[name="op"][type="submit"]') || form.querySelector('input[name="op"]');
            if (op) op.disabled = false;
            form.submit();
        }""", provider)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        html_text = page.content()
        rows = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S):
            cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            cells = [c for c in cells if c]
            if len(cells) >= 5 and re.match(r"^\d{6,8}$", cells[3].replace(" ", "")):
                rows.append({"name": re.sub(r"\s*See registration details$", "", cells[0]),
                             "owner": cells[1], "address": cells[2],
                             "regno": cells[3].replace(" ", ""), "status": cells[4]})
        if not rows:
            out["error"] = "no results"
            return out
        best = max(rows, key=lambda r: difflib.SequenceMatcher(None, provider.lower(), r["name"].lower()).ratio())
        score = difflib.SequenceMatcher(None, provider.lower(), best["name"].lower()).ratio()
        out.update({"registered_name": best["name"], "owner": best["owner"],
                    "address": best["address"], "number": best["regno"],
                    "status": best["status"], "match": round(score, 2),
                    "url": f"{BASE}/registers/pharmacy/registrationnumber/{best['regno']}",
                    "verified": best["status"].lower().startswith("registered") and score >= 0.55})
    except Exception as exc:
        out["error"] = str(exc)[:60]
    return out


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    providers = [p["provider"] for p in index["providers"]] + [u["provider"] for u in index.get("unread", [])]

    numbers: dict[str, str] = {}
    for p in json.loads((SCRATCH / "provider_list.json").read_text()):
        if p.get("gphc"):
            numbers.setdefault(p["provider"], p["gphc"])
    for line in (SCRATCH / "crawl_raw.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("gphc"):
                numbers.setdefault(r["provider"], str(r["gphc"]).strip())
    lj = json.loads(Path("/Users/PetroulaKostofska/mounjaro-find-uk-github/data/snapshots/latest.json").read_text())
    for p in lj["providers"]:
        g = p.get("gphc_registration_number")
        if g:
            numbers.setdefault(p["provider"], str(g).strip())

    results: dict[str, dict] = {}
    known = [(n, numbers[n]) for n in providers if n in numbers]
    unknown = [n for n in providers if n not in numbers]
    print(f"verifying {len(known)} by registration number, {len(unknown)} by name search")

    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(lambda pair: by_number(*pair), known):
            results[res["provider"]] = res
            time.sleep(0.1)

    retry = [n for n in providers if not results.get(n, {}).get("verified")]
    unknown = sorted(set(unknown) | set(retry))

    if unknown:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=UA, locale="en-GB")
            page = ctx.new_page()
            for name in unknown:
                res = search_by_name(page, name)
                prior = results.get(name, {})
                if res.get("verified") and (not prior.get("verified") or res.get("match", 0) >= prior.get("match", 0)):
                    res["method"] = "search"
                    results[name] = res
                elif prior:
                    prior["search_attempt"] = {k: res.get(k) for k in ("registered_name", "number", "match", "error")}
                    results[name] = prior
                else:
                    results[name] = res
                print(f"  search {name:<24} -> {res.get('registered_name','—')} ({res.get('number')}) match={res.get('match','—')}",
                      flush=True)
                time.sleep(1.0)
            ctx.close()
            browser.close()

    payload = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": "General Pharmaceutical Council register (pharmacyregulation.org)",
               "providers": results}
    (APP / "gphc.json").write_text(json.dumps(payload, indent=1))

    ok = sum(1 for r in results.values() if r.get("verified"))
    print(f"\nwrote gphc.json — {ok}/{len(results)} verified as registered")
    bad = [(n, r.get("status") or r.get("error")) for n, r in results.items() if not r.get("verified")]
    for n, s in bad:
        print(f"  not verified: {n:<26} {s}")


if __name__ == "__main__":
    main()
