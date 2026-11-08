#!/usr/bin/env python3
"""Find Mounjaro product pages via each pharmacy's sitemap, then read prices."""
import html, json, re, ssl, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
JRNL = Path("/Users/PetroulaKostofska/.hermes/cache/scratch/crawl_raw.jsonl")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
FWD = re.compile(r"(2\.5|5|7\.5|10|12\.5|15)\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
REV = re.compile(r"\u00a3\s?(\d{2,3}(?:\.\d{2})?)[^\u00a3]{0,110}?(2\.5|5|7\.5|10|12\.5|15)\s?mg", re.I)
SITEMAPS = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap_products_1.xml", "/product-sitemap.xml"]


def get(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return r.read(2_000_000).decode("utf-8", "replace")
    except Exception:
        return ""


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


def probe(entry: dict) -> dict:
    name, domain = entry["provider"], entry.get("domain") or ""
    out = {"provider": name, "url": "", "prices": {}, "found_in_sitemap": 0}
    if not domain:
        return out
    urls: list[str] = []
    for path in SITEMAPS:
        body = get(f"https://{domain}{path}")
        if not body:
            continue
        # follow one level of sitemap index
        children = re.findall(r"<loc>\s*([^<\s]+sitemap[^<\s]*)\s*</loc>", body, re.I)
        for child in children[:4]:
            body2 = get(child)
            urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body2, re.I)
        urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.I)
        if urls:
            break
    mj = [u for u in dict.fromkeys(urls) if re.search(r"mounjaro", u, re.I)]
    out["found_in_sitemap"] = len(mj)
    best: dict[str, float] = {}
    for url in mj[:4]:
        found = pairs(text_of(get(url)))
        if len(found) > len(best):
            best, out["url"] = found, url
        if len(found) >= 5:
            break
    out["prices"] = best
    return out


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    todo = [u for u in index["unread"] if u.get("domain")]
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(probe, todo):
            results.append(res)
            flag = "PRICE" if len(res["prices"]) >= 3 else ("partial" if res["prices"] else "-")
            print(f"{res['provider']:<24} {flag:<8} doses={len(res['prices'])} sitemap_hits={res['found_in_sitemap']} "
                  f"{res['url'][:56]}", flush=True)
    rec = [r for r in results if len(r["prices"]) >= 3]
    print(f"\nrecovered via sitemap: {len(rec)}/{len(results)} — " + ", ".join(r["provider"] for r in rec))
    if rec:
        rows = {}
        if JRNL.exists():
            for line in JRNL.read_text().splitlines():
                if line.strip():
                    row = json.loads(line); rows[row["provider"]] = row
        for r in rec:
            rows[r["provider"]] = {"provider": r["provider"], "domain": "", "prices": r["prices"],
                                   "page": r["url"], "status": f"200/{len(r['prices'])}",
                                   "note": "recovered via sitemap",
                                   "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        for u in index["unread"]:
            if u["provider"] in rows:
                rows[u["provider"]]["domain"] = u.get("domain", "")
        JRNL.write_text("\n".join(json.dumps(v) for v in rows.values()) + "\n")
        print("journal updated:", len(rows))


if __name__ == "__main__":
    main()
