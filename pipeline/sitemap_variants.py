#!/usr/bin/env python3
"""Sitemap-first price hunt: find the Mounjaro product pages a shop already
publishes, then read prices from variant data, JSON-LD or the page text."""
import html, json, re, ssl, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
JRNL = Path("/Users/PetroulaKostofska/.hermes/cache/scratch/crawl_raw.jsonl")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()

# Pages that talk about prices without being the pharmacy's own price list:
# comparison articles, buying guides, blog posts. Curely publishes a "Mounjaro
# Price Comparison By Dose" article quoting market averages and rivals' prices —
# reading it as their own would poison the index.
NOT_OUR_PRICES = re.compile(r"(comparison|price-?guide|best-|guide|blog|news|advice|"
                            r"supplement|article|review)", re.I)

DOSES = {"2.5", "5", "7.5", "10", "12.5", "15"}
DOSE = re.compile(r"(\d+(?:\.\d+)?)\s*mg", re.I)
FWD = re.compile(r"(2\.5|5|7\.5|10|12\.5|15)\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
REV = re.compile(r"\u00a3\s?(\d{2,3}(?:\.\d{2})?)[^\u00a3]{0,110}?(2\.5|5|7\.5|10|12\.5|15)\s?mg", re.I)
SM = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap_products_1.xml", "/product-sitemap.xml", "/wp-sitemap.xml"]

def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return r.status, r.read(2_000_000).decode("utf-8", "replace")
    except Exception:
        return 0, ""

def num(p):
    try:
        v = float(str(p).replace("£","").replace(",","").strip())
        return v if 50 <= v <= 500 else None
    except Exception:
        return None

def from_woo(b):
    m = re.search(r'data-product_variations="([^"]+)"', b)
    if not m: return {}
    try: data = json.loads(html.unescape(m.group(1)))
    except Exception: return {}
    out = {}
    for v in data:
        lab = " ".join(str(x) for x in (v.get("attributes") or {}).values())
        h = DOSE.search(lab); p = num(v.get("display_price"))
        if h and p and h.group(1) in DOSES: out.setdefault(h.group(1), p)
    return out

def from_shopify(b, base):
    out = {}
    for handle in list(dict.fromkeys(re.findall(r"/products/([a-z0-9\-]*mounjaro[a-z0-9\-]*)", b, re.I)))[:4]:
        s, js = get(f"{base}/products/{handle}.js")
        if s != 200 or not js: continue
        try: d = json.loads(js)
        except Exception: continue
        for v in d.get("variants", []):
            h = DOSE.search(v.get("title","")); p = num((v.get("price") or 0)/100)
            if h and p and h.group(1) in DOSES: out.setdefault(h.group(1), p)
    return out

def from_jsonld(b):
    out = {}
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', b, re.S|re.I):
        try: d = json.loads(m.group(1))
        except Exception: continue
        for item in (d if isinstance(d, list) else [d]):
            if not isinstance(item, dict): continue
            blob = json.dumps(item); h = DOSE.search(blob)
            offers = item.get("offers") or []
            if isinstance(offers, dict): offers = [offers]
            for o in offers:
                p = num(o.get("price"))
                if h and p and h.group(1) in DOSES: out.setdefault(h.group(1), p); break
    return out

def from_text(b):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S|re.I)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    out = {}
    for m in FWD.finditer(t): out.setdefault(m.group(1), float(m.group(2)))
    for m in REV.finditer(t): out.setdefault(m.group(2), float(m.group(1)))
    return {d: p for d, p in out.items() if 50 <= p <= 500}

def sitemap_urls(domain):
    urls = []
    for p in SM:
        s, b = get(f"https://{domain}{p}")
        if s != 200 or not b: continue
        kids = re.findall(r"<loc>\s*([^<\s]*sitemap[^<\s]*)\s*</loc>", b, re.I)
        for k in kids[:6]:
            s2, b2 = get(k)
            if s2 == 200: urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", b2, re.I)
        urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", b, re.I)
        if urls: break
    keep = [u for u in dict.fromkeys(urls)
            if re.search(r"mounjaro", u, re.I) and not NOT_OUR_PRICES.search(u)]
    return keep[:12]

def probe(entry):
    name, domain = entry["provider"], entry.get("domain","")
    out = {"provider": name, "domain": domain, "prices": {}, "url": "", "how": ""}
    if not domain: return out
    base = f"https://{domain}"
    for url in sitemap_urls(domain):
        s, b = get(url)
        if s != 200 or not b: continue
        for how, found in (("woocommerce", from_woo(b)), ("shopify", from_shopify(b, base)),
                           ("json-ld", from_jsonld(b)), ("page text", from_text(b))):
            if len(found) > len(out["prices"]):
                out["prices"], out["url"], out["how"] = found, url, how
        if len(out["prices"]) >= 4: break
    return out

def main():
    idx = json.loads((APP/"price-index.json").read_text())
    todo = [u for u in idx["unread"] if u.get("domain")]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(probe, todo))
    for r in results:
        print(f"{r['provider']:<24} doses={len(r['prices'])} {r['how']:<14} {r['url'][:56]}", flush=True)
    rec = [r for r in results if len(r["prices"]) >= 3]
    print(f"\nrecovered {len(rec)}/{len(results)}: " + ", ".join(r["provider"] for r in rec))
    if rec:
        rows = {}
        for line in JRNL.read_text().splitlines():
            if line.strip():
                row = json.loads(line); rows[row["provider"]] = row
        for r in rec:
            rows[r["provider"]] = {"provider": r["provider"], "domain": r["domain"], "prices": r["prices"],
                "page": r["url"], "status": f"200/{len(r['prices'])}",
                "note": f"read from published product page ({r['how']})",
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        JRNL.write_text("\n".join(json.dumps(v) for v in rows.values()) + "\n")
        print("journal now holds", len(rows))

if __name__ == "__main__":
    main()
