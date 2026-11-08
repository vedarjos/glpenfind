#!/usr/bin/env python3
"""Fetch each pharmacy's own Trustpilot score from Trustpilot, not from anyone's table.

Reads price-index.json for the domains we index, opens the public review page in a
real browser (Trustpilot 403s plain HTTP clients), and pulls the JSON-LD rating.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")


def scores(text: str) -> tuple[float | None, int | None]:
    rating = count = None
    for block in re.findall(r'"ratingValue"\s*:\s*"?([\d.]+)"?', text):
        try:
            rating = float(block)
            break
        except ValueError:
            pass
    for block in re.findall(r'"(?:reviewCount|ratingCount)"\s*:\s*"?(\d+)"?', text):
        count = int(block)
        break
    return rating, count


def fetch(domain: str) -> tuple[str, float | None, int | None]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB")
        page = ctx.new_page()
        try:
            page.goto(f"https://uk.trustpilot.com/review/{domain}", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(1800)
            rating, count = scores(page.content())
            return domain, rating, count
        except Exception:
            return domain, None, None
        finally:
            ctx.close()
            browser.close()


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    domains = sorted({p["domain"] for p in index["providers"] if p.get("domain")})
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for domain, rating, count in pool.map(fetch, domains):
            out[domain] = {"rating": rating, "reviews": count}
            print(f"  {domain[:38]:<38} {rating} ({count})", flush=True)

    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": "uk.trustpilot.com public review pages", "by_domain": out}
    (APP / "ratings.json").write_text(json.dumps(payload, indent=1))
    got = sum(1 for v in out.values() if v["rating"])
    print(f"\nwrote ratings.json — {got}/{len(domains)} with a score")


if __name__ == "__main__":
    main()
