#!/usr/bin/env python3
"""Pull the non-price facts out of each priced pharmacy's own pages.

For every pharmacy with a verified price, collect evidence snippets for:
  - BMI eligibility
  - delivery window / cost
  - first-order discount codes
  - photo requirements
  - consultation length, if stated

Writes reports/detail-snippets.json and prints a compact digest. Nothing is
inferred: a field with no snippet is reported as unknown.
"""
from __future__ import annotations

import html
import json
import re
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
ART = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/crawl-artifacts")
OUT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/reports/detail-snippets.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()

FIELDS = {
    "bmi": [
        r"BMI[^.]{0,120}",
        r"body mass index[^.]{0,120}",
    ],
    "delivery": [
        r"[^.]{0,90}(?:next[- ]day|next working day|24 hours|48 hours|same day|free delivery|free shipping|delivery is free)[^.]{0,90}",
    ],
    "discount": [
        r"[^.]{0,80}(?:£\s?\d{1,3}\s?off|% off|use code|promo code|discount code|first order)[^.]{0,90}",
    ],
    "photo": [
        r"[^.]{0,100}(?:full[- ]body photo|photo of you|photograph|upload a photo|dated photo|picture of yourself|weighing scale)[^.]{0,100}",
    ],
}


def clean_text(body: str) -> str:
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return re.sub(r"\s+", " ", text)


def scan(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for field, pats in FIELDS.items():
        hits: list[str] = []
        for pat in pats:
            for m in re.finditer(pat, text, re.I):
                snippet = m.group(0).strip()
                if len(snippet) < 25:
                    continue
                if not any(snippet[:45] in h for h in hits):
                    hits.append(snippet)
                if len(hits) >= 4:
                    break
            if len(hits) >= 4:
                break
        found[field] = hits[:3]
    return found


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-GB,en"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            return clean_text(r.read(1_500_000).decode("utf-8", "replace"))
    except Exception as exc:
        return f"__ERROR__{exc}"


def for_provider(entry: dict) -> dict:
    name = entry["provider"]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    texts: list[tuple[str, str]] = []

    art = ART / f"{slug}.html"
    if art.exists():
        texts.append((f"artifact:{art.name}", clean_text(art.read_text(encoding="utf-8", errors="replace"))))

    url = entry.get("source_url") or ""
    if url:
        body = fetch(url)
        if not body.startswith("__ERROR__"):
            texts.append((url, body))
        else:
            texts.append(("error", body))

    merged = {f: [] for f in FIELDS}
    sources: dict[str, list[str]] = {f: [] for f in FIELDS}
    for src, text in texts:
        if not text or text.startswith("__ERROR__"):
            continue
        for field, hits in scan(text).items():
            for h in hits:
                if not any(h[:45] in x for x in merged[field]):
                    merged[field].append(h)
                    sources[field].append(src)

    return {"provider": name, "fields": {f: {"snippets": merged[f][:3], "sources": sources[f][:3]}
                                         for f in FIELDS},
            "pages": [s for s, _ in texts]}


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    rows = index["providers"]
    out = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(for_provider, rows):
            out.append(res)
            counts = {f: len(res["fields"][f]["snippets"]) for f in FIELDS}
            print(f"{res['provider']:<26} " + " ".join(f"{k}={v}" for k, v in counts.items()), flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
