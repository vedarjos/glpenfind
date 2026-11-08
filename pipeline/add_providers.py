#!/usr/bin/env python3
"""Crawl a specific list of pharmacies and append to the crawl journal.

Same extraction rules as crawl_all_providers.py, but writes artifacts outside
the app bundle and never overwrites existing journal rows.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRATCH = Path("/Users/PetroulaKostofska/.hermes/cache/scratch")
ART = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/crawl-artifacts")
JRNL = SCRATCH / "crawl_raw.jsonl"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
DOSE = r"(2\.5|5|7\.5|10|12\.5|15)"
FWD = re.compile(DOSE + r"\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
REV = re.compile(r"\u00a3\s?(\d{2,3}(?:\.\d{2})?)[^\u00a3]{0,110}?" + DOSE + r"\s?mg", re.I)

# --- per-site parsers -------------------------------------------------------
# Site-specific layouts that defeat a generic dose->price pairing go here.
# Oxford renders prices as a positional table: a dose header row, then a
# "1 units" row whose columns line up with it.
def parse_oxford(text: str) -> dict[str, float]:
    m = re.search(r"2\.5mg\s*5mg\s*7\.5mg\s*10mg\s*12\.5mg\s*15mg\s*1\s*units(.{0,400}?)2\s*units", text, re.S | re.I)
    if not m:
        return {}
    prices = re.findall(r"£\s?(\d{2,3}(?:\.\d{2})?)", m.group(1))
    doses = ["2.5", "5", "7.5", "10", "12.5", "15"]
    out = {d: float(p) for d, p in zip(doses, prices)}
    return {d: v for d, v in out.items() if 80 <= v <= 400}


SPECIAL = {"Oxford Online Pharmacy": parse_oxford}


def extract(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for m in FWD.finditer(text):
        found.setdefault(m.group(1), float(m.group(2)))
    for m in REV.finditer(text):
        found.setdefault(m.group(2), float(m.group(1)))
    return {d: p for d, p in found.items() if 80 <= p <= 400}


def crawl(provider: str, domain: str) -> dict:
    row = {"provider": provider, "domain": domain, "prices": {}, "page": "",
           "status": "", "note": "",
           "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB", viewport={"width": 1366, "height": 1000})
        page = ctx.new_page()
        try:
            start = domain if domain.startswith("http") else f"https://{domain}/"
            resp = page.goto(start, wait_until="domcontentloaded", timeout=25000)
            row["status"] = str(resp.status if resp else "?")
            page.wait_for_timeout(2500)
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            targets, seen = [], set()
            if domain.count("/") > 2 and not domain.startswith("http://"):
                pass
            if re.search(r"mounjaro", start, re.I):
                targets = [start.split("?")[0].rstrip("/")]
            for h in hrefs:
                if not re.search(r"mounjaro", h, re.I):
                    continue
                h = h.split("?")[0].rstrip("/")
                if h in seen or re.search(r"(blog|news|guide|review|discount-code)", h, re.I):
                    continue
                seen.add(h)
                targets.append(h)
            best = (0, {}, "")
            for url in targets[:5]:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)
                    text = page.inner_text("body")[:500_000]
                    special = SPECIAL.get(provider)
                    found = special(text) if special else extract(text)
                    if len(found) > best[0]:
                        best = (len(found), found, url)
                        ART.mkdir(parents=True, exist_ok=True)
                        slug = re.sub(r"[^a-z0-9]+", "-", provider.lower()).strip("-")
                        (ART / f"{slug}.html").write_text(page.content()[:2_000_000], encoding="utf-8")
                    if len(found) >= 5:
                        break
                except Exception:
                    continue
            count, prices, url = best
            row["prices"], row["page"] = prices, url
            row["note"] = f"{len(targets)} mounjaro links"
            row["status"] = f"{row['status']}/{count}"
        except Exception as exc:
            row["status"], row["note"] = "error", str(exc)[:70]
        finally:
            ctx.close()
            browser.close()
    return row


def main(pairs: list[tuple[str, str]]) -> None:
    existing = {}
    if JRNL.exists():
        for line in JRNL.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                existing[r["provider"]] = r
    for name, domain in pairs:
        r = crawl(name, domain)
        existing[name] = r
        print(f"{name:<26} doses={len(r['prices'])} status={r['status']}  {r['page'][:60]}", flush=True)
    JRNL.write_text("\n".join(json.dumps(r) for r in existing.values()) + "\n")
    print(f"journal now holds {len(existing)} providers")


if __name__ == "__main__":
    pairs = [tuple(a.split("=")) for a in sys.argv[1:]]
    main(pairs)
