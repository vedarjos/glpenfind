#!/usr/bin/env python3
"""Read per-dose prices from shop product pages instead of consultation forms.

Many "gated" pharmacies are ordinary shops: the price table is the variant data
behind a dose selector, which never appears in page text. Two shapes cover most
of the UK market:

  WooCommerce  -> <form class="variations_form" data-product_variations='[...]'>
  Shopify      -> /products/<handle>.js  -> variants[].title / .price

No account, no questionnaire, no personal data: just the product page the shop
publishes for anyone.
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
JRNL = Path("/Users/PetroulaKostofska/.hermes/cache/scratch/crawl_raw.jsonl")
REPORT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/reports/variant-probe.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
DOSE = re.compile(r"(\d+(?:\.\d+)?)\s*mg", re.I)

# Pages that talk about prices without being the pharmacy's own price list:
# comparison articles, buying guides, blog posts. Curely publishes a "Mounjaro
# Price Comparison By Dose" article quoting market averages and rivals' prices —
# reading it as their own would poison the index.
NOT_OUR_PRICES = re.compile(r"(comparison|price-?guide|best-|guide|blog|news|advice|"
                            r"supplement|article|review)", re.I)

DOSES = {"2.5", "5", "7.5", "10", "12.5", "15"}


def get(url: str, raw: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-GB,en"})
    try:
        with urllib.request.urlopen(req, timeout=18, context=CTX) as r:
            body = r.read(2_000_000).decode("utf-8", "replace")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def normalise(price) -> float | None:
    try:
        v = float(str(price).replace("£", "").replace(",", "").strip())
    except Exception:
        return None
    return v if 50 <= v <= 500 else None


def woo_variants(body: str) -> dict[str, float]:
    m = re.search(r'data-product_variations="([^"]+)"', body)
    if not m:
        return {}
    try:
        data = json.loads(html.unescape(m.group(1)))
    except Exception:
        return {}
    out: dict[str, float] = {}
    for v in data:
        label = " ".join(str(x) for x in (v.get("attributes") or {}).values())
        hit = DOSE.search(label)
        price = normalise(v.get("display_price"))
        if hit and price and hit.group(1) in DOSES:
            out.setdefault(hit.group(1), price)
    return out


def shopify_variants(body: str, base: str) -> dict[str, float]:
    handles = re.findall(r"/products/([a-z0-9\-]*mounjaro[a-z0-9\-]*)", body, re.I)
    out: dict[str, float] = {}
    for handle in list(dict.fromkeys(handles))[:3]:
        status, js = get(f"{base}/products/{handle}.js")
        if status != 200 or not js:
            continue
        try:
            data = json.loads(js)
        except Exception:
            continue
        for v in data.get("variants", []):
            hit = DOSE.search(v.get("title", ""))
            price = normalise((v.get("price") or 0) / 100)
            if hit and price and hit.group(1) in DOSES:
                out.setdefault(hit.group(1), price)
        if len(out) >= 3:
            break
    return out


def jsonld_offers(body: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', body, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            text = json.dumps(item)
            hit = DOSE.search(text)
            price = None
            for offer in (item.get("offers") or []) if isinstance(item, dict) else []:
                price = normalise(offer.get("price"))
                if price:
                    break
            if hit and price and hit.group(1) in DOSES:
                out.setdefault(hit.group(1), price)
    return out


def candidate_urls(domain: str, body: str) -> list[str]:
    urls = []
    for href in re.findall(r'href="([^"]+)"', body):
        if re.search(r"mounjaro", href, re.I) and re.search(r"shop|product|treatment|buy|medication", href, re.I):
            full = href if href.startswith("http") else f"https://{domain}{href if href.startswith('/') else '/' + href}"
            if domain in full and full not in urls:
                urls.append(full.split("?")[0])
    return urls[:5]


def probe(entry: dict) -> dict:
    name, domain = entry["provider"], entry.get("domain", "")
    out = {"provider": name, "domain": domain, "prices": {}, "url": "", "how": ""}
    if not domain:
        return out
    base = f"https://{domain}"
    for path in ("", "/shop", "/treatments", "/weight-loss"):
        status, body = get(base + path)
        if status != 200 or not body:
            continue
        pages = candidate_urls(domain, body)[:4]
        for url in pages + [base + path]:
            s2, b2 = get(url) if url != base + path else (status, body)
            if s2 != 200 or not b2:
                continue
            for how, fn in (("woocommerce-variations", woo_variants), ("json-ld-offers", jsonld_offers)):
                found = fn(b2)
                if len(found) > len(out["prices"]):
                    out["prices"], out["url"], out["how"] = found, url, how
            found = shopify_variants(b2, base)
            if len(found) > len(out["prices"]):
                out["prices"], out["url"], out["how"] = found, url, "shopify-variants"
            if len(out["prices"]) >= 4:
                return out
    return out


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    todo = [u for u in index["unread"] if u.get("domain")]
    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        for res in pool.map(probe, todo):
            results.append(res)
            print(f"{res['provider']:<24} doses={len(res['prices'])} {res['how']:<22} {res['url'][:52]}", flush=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=1))

    rec = [r for r in results if len(r["prices"]) >= 3]
    print(f"\nrecovered {len(rec)}/{len(results)}: " + ", ".join(r["provider"] for r in rec))
    if rec:
        rows = {}
        if JRNL.exists():
            for line in JRNL.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    rows[row["provider"]] = row
        for r in rec:
            rows[r["provider"]] = {
                "provider": r["provider"], "domain": r["domain"], "prices": r["prices"],
                "page": r["url"], "status": f"200/{len(r['prices'])}",
                "note": f"read from shop variant data ({r['how']}), no account needed",
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        JRNL.write_text("\n".join(json.dumps(v) for v in rows.values()) + "\n")
        print(f"journal now holds {len(rows)}")


if __name__ == "__main__":
    main()
