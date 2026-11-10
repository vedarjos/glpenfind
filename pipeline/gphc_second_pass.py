#!/usr/bin/env python3
"""Second pass for pharmacies whose registration number was not found by plain HTTP.

Renders each site in a browser (footers are often injected by JS), also checks the
HTML artifacts we already captured, then verifies any candidate on the register.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
ART = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/crawl-artifacts")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
PATTERNS = [re.compile(r"gphc[^0-9]{0,45}?(\d{7})", re.I),
            re.compile(r"registration\s*(?:number|no\.?)[^0-9]{0,30}?(\d{7})", re.I),
            re.compile(r"pharmacyregulation\.org/registers/pharmacy/(?:registrationnumber/)?(\d{7})", re.I)]
PAGES = ["", "/privacy-policy", "/terms-and-conditions", "/legal", "/about-us", "/contact-us", "/pages/terms-of-service"]


def scan(text: str) -> list[str]:
    out = []
    for pat in PATTERNS:
        for m in pat.finditer(text):
            if m.group(1) not in out:
                out.append(m.group(1))
    return out


def main() -> None:
    data = json.loads((APP / "gphc.json").read_text())
    provs = data["providers"]
    index = json.loads((APP / "price-index.json").read_text())
    domains = {p["provider"]: p.get("domain", "") for p in index["providers"]}
    domains.update({u["provider"]: u.get("domain", "") for u in index.get("unread", [])})
    misses = [n for n, r in provs.items() if not r.get("verified")]

    found: dict[str, tuple[str, str]] = {}
    # 1) artifacts already captured
    for name in misses:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        art = ART / f"{slug}.html"
        if art.exists():
            text = html.unescape(re.sub(r"<[^>]+>", " ", art.read_text(encoding="utf-8", errors="replace")))
            nums = scan(text)
            if nums:
                found[name] = (nums[0], f"artifact:{art.name}")

    # 2) render the site
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB")
        page = ctx.new_page()
        for name in misses:
            if name in found or not domains.get(name):
                continue
            for path in PAGES:
                try:
                    page.goto(f"https://{domains[name]}{path}", wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1200)
                    nums = scan(page.inner_text("body"))
                    if nums:
                        found[name] = (nums[0], f"https://{domains[name]}{path}")
                        break
                except Exception:
                    continue
        ctx.close()
        browser.close()

    print(f"second pass found numbers for {len(found)} of {len(misses)}")
    for n, (num, where) in found.items():
        print(f"  {n:<26} {num}  ({where[:60]})")
    (APP / "gphc_candidates.json").write_text(json.dumps(found, indent=1))


if __name__ == "__main__":
    main()
