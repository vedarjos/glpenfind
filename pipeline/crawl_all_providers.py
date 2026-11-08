#!/usr/bin/env python3
"""Provider-direct Mounjaro price crawler (no aggregator data).

For each pharmacy domain: open homepage in headless Chromium, find the Mounjaro
product page, render it, and extract dose -> GBP price pairs. Only providers
where >= 4 distinct doses pair with a price are kept as high confidence.

Writes:
  price-index.json   usable app data (with provenance per row)
  crawl-artifacts/   rendered HTML per provider, for later review
"""
from __future__ import annotations

import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRATCH = Path("/Users/PetroulaKostofska/.hermes/cache/scratch")
OUT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www")
ART = OUT / "crawl-artifacts"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")

DOSE_VALUES = ["2.5", "5", "7.5", "10", "12.5", "15"]
DOSE = r"(2\.5|5|7\.5|10|12\.5|15)"
FWD = re.compile(DOSE + r"\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
REV = re.compile(r"\u00a3\s?(\d{2,3}(?:\.\d{2})?)[^\u00a3]{0,110}?" + DOSE + r"\s?mg", re.I)

EXTRA_DOMAINS = {
    "Medicine Marketplace": "treatments.medicinemarketplace.com",
    "Fylde Clinic": "fyldeclinic.co.uk",
    "Cuva Health": "cuvahealth.co.uk",
    "DoToR": "dotor.co.uk",
    "Everwell": "joineverwell.com",
    "Pharmacy2U": "pharmacy2u.co.uk",
    "Pills2U": "pills2u.co.uk",
    "Swift Doctor": "swiftdoctor.co.uk",
    "Get Weightloss": "getweightloss.co.uk",
    "OnlineMeds": "onlinemeds.co.uk",
}


def sanitize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def extract(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for m in FWD.finditer(text):
        found.setdefault(m.group(1), float(m.group(2)))
    for m in REV.finditer(text):
        found.setdefault(m.group(2), float(m.group(1)))
    # sanity: Mounjaro in the UK sits between £80 and £400 per pen
    return {d: p for d, p in found.items() if 80 <= p <= 400}


def crawl(provider: str, domain: str) -> dict:
    row = {"provider": provider, "domain": domain, "prices": {}, "page": "",
           "status": "", "note": "", "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if not domain:
        row["status"] = "no_domain"
        return row
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB", viewport={"width": 1366, "height": 1000})
        page = ctx.new_page()
        try:
            resp = page.goto(f"https://{domain}/", wait_until="domcontentloaded", timeout=25000)
            row["status"] = str(resp.status if resp else "?")
            page.wait_for_timeout(2500)
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            mj = [h for h in hrefs if re.search(r"mounjaro", h, re.I)]
            seen, targets = set(), []
            for h in mj:
                h = h.split("?")[0].rstrip("/")
                if h not in seen and not re.search(r"(blog|news|guide|review|discount-code)", h, re.I):
                    seen.add(h)
                    targets.append(h)
            best: tuple[int, dict[str, float], str] = (0, {}, "")
            for url in targets[:4]:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)
                    text = page.inner_text("body")[:500_000]
                    found = extract(text)
                    if len(found) > best[0]:
                        best = (len(found), found, url)
                        ART.mkdir(parents=True, exist_ok=True)
                        (ART / f"{sanitize(provider)}.html").write_text(page.content()[:2_000_000], encoding="utf-8")
                    if len(found) >= 5:
                        break
                except Exception:
                    continue
            count, prices, url = best
            row["prices"] = prices
            row["page"] = url or ""
            row["note"] = f"{len(targets)} mounjaro links found"
            row["status"] = f"{row['status']}/{count}"
        except Exception as exc:
            row["status"] = "error"
            row["note"] = str(exc)[:70]
        finally:
            ctx.close()
            browser.close()
    return row


def main() -> None:
    providers = json.loads((SCRATCH / "provider_list.json").read_text())
    for p in providers:
        if not p.get("domain") and p["provider"] in EXTRA_DOMAINS:
            p["domain"] = EXTRA_DOMAINS[p["provider"]]

    JRNL = SCRATCH / "crawl_raw.jsonl"
    done = set()
    if JRNL.exists():
        for line in JRNL.read_text().splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["provider"])
                except Exception:
                    pass
    providers = [p for p in providers if p["provider"] not in done]
    print(f"resuming with {len(providers)} remaining")

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(crawl, p["provider"], p.get("domain", "")): p for p in providers}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            r["gphc"] = futs[f].get("gphc", "")
            results.append(r)
            with JRNL.open("a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(f"  [{i:>2}/{len(providers)}] {r['provider'][:26]:<26} doses={len(r['prices'])} status={r['status']}", flush=True)

    # merge with anything from an earlier partial run
    for line in (SCRATCH / "crawl_raw.jsonl").read_text().splitlines():
        if line.strip():
            results.append(json.loads(line))
    dedup = {}
    for r in results:
        dedup[r["provider"]] = r
    results = list(dedup.values())

    results.sort(key=lambda r: (-len(r["prices"]), r["provider"]))
    strong = [r for r in results if len(r["prices"]) >= 4]
    weak = [r for r in results if 1 <= len(r["prices"]) < 4]
    print(f"\nstrong(>=4 doses): {len(strong)}   weak: {len(weak)}   none: {len(results)-len(strong)-len(weak)}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": "provider-direct crawl of pharmacy websites (headless Chromium); no aggregator database used",
        "doses": DOSE_VALUES,
        "providers": [
            {
                "provider": r["provider"],
                "gphc": r["gphc"],
                "domain": r["domain"],
                "prices_gbp": r["prices"],
                "source_url": r["page"],
                "retrieved_at": r["retrieved_at"],
                "confidence": "high" if len(r["prices"]) >= 4 else ("medium" if r["prices"] else "none"),
                "checks": len(r["prices"]),
            }
            for r in results if r["prices"]
        ],
    }
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "data" / "price-index.json").write_text(json.dumps(payload, indent=1))
    (SCRATCH / "crawl_raw.json").write_text(json.dumps(results, indent=1))
    print("wrote", OUT / "data" / "price-index.json", "providers with prices:", len(payload["providers"]))


if __name__ == "__main__":
    main()
