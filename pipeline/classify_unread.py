#!/usr/bin/env python3
"""Classify the pharmacies we still cannot read.

For each, render the site in a browser and decide which of these is true:
  publishes_price   - a dose/price pair appears without any sign-in or consultation
  gated             - the price only appears after starting a consultation or signing in
  js_blocked        - the page needs JS we could not execute, or challenged us
  no_price_found    - the product page genuinely shows no price

Writes reports/unread-classification.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
OUT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/reports/unread-classification.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
FWD = re.compile(r"(2\.5|5|7\.5|10|12\.5|15)\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
REV = re.compile(r"\u00a3\s?(\d{2,3}(?:\.\d{2})?)[^\u00a3]{0,110}?(2\.5|5|7\.5|10|12\.5|15)\s?mg", re.I)
GATE = re.compile(r"(start (your )?consultation|complete (the |your )?(online )?(consultation|assessment)|"
                  r"sign in to (see|view)|log ?in to (see|view)|price(s)? (shown|revealed) after|"
                  r"answer a few questions to (see|get))", re.I)


def pairs(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for m in FWD.finditer(text):
        found.setdefault(m.group(1), float(m.group(2)))
    for m in REV.finditer(text):
        found.setdefault(m.group(2), float(m.group(1)))
    return {d: p for d, p in found.items() if 80 <= p <= 400}


def classify(page, name: str, domain: str) -> dict:
    out = {"provider": name, "domain": domain, "class": "unknown", "prices": {}, "url": ""}
    try:
        resp = page.goto(f"https://{domain}/", wait_until="domcontentloaded", timeout=25000)
        out["home_status"] = resp.status if resp else 0
        page.wait_for_timeout(2000)
        text = page.inner_text("body")
        gate = bool(GATE.search(text))

        links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        targets = []
        for h in links:
            if re.search(r"mounjaro", h, re.I) and not re.search(r"(blog|news|guide|review)", h, re.I):
                clean = h.split("?")[0]
                if clean not in targets:
                    targets.append(clean)

        best = {}
        best_url = ""
        for url in targets[:4]:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2500)
                t = page.inner_text("body")
                found = pairs(t)
                if len(found) > len(best):
                    best, best_url = found, url
                if len(found) >= 5:
                    break
            except Exception:
                continue
        if not best and not targets:
            found = pairs(text)
            if found:
                best, best_url = found, f"https://{domain}/"
        out["prices"], out["url"] = best, best_url
        out["gated_language"] = gate
        if len(best) >= 3:
            out["class"] = "publishes_price"
        elif gate:
            out["class"] = "gated"
        elif targets:
            out["class"] = "no_price_found"
        else:
            out["class"] = "js_blocked"
    except Exception as exc:
        out["class"] = "error"
        out["error"] = str(exc)[:80]
    return out


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    todo = [(u["provider"], u.get("domain", "")) for u in index["unread"] if u.get("domain")]
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB", viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        for name, domain in todo:
            res = classify(page, name, domain)
            results.append(res)
            print(f"{name:<24} {res['class']:<16} doses={len(res['prices'])} gate={res.get('gated_language')} "
                  f"{res.get('url','')[:52]}", flush=True)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(results, indent=1))
        ctx.close()
        browser.close()
    print(f"\nwrote {OUT} ({len(results)} providers)")


if __name__ == "__main__":
    main()
