"""Re-read pharmacies that only ever yielded one or two doses.

The original crawler used a single text regex: `(2\\.5|5|7\\.5|10|12\\.5|15)\\s?mg`.
That misses `5.0mg` (a very common spelling) and, worse, lets the `12.5mg` label
match as `2.5mg`. Pages that list every dose therefore landed in the index with
just their starting dose, which made the 7.5mg list look four-fifths full.

This pass re-reads only the under-covered providers, with a corrected pattern and
a tag-stripped fallback, and merges **only if it finds more doses**. It can add a
dose; it can never remove one, and it never touches `unread` or
`removed_for_compliance`.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / 'www' / 'data' / 'price-index.json'
REPORT_DIR = ROOT / 'reports'

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

DOSE_VALUES = ['2.5', '5', '7.5', '10', '12.5', '15']
# (?!\d) stops "10" matching inside "100"; (?<![\d.]) stops "2.5" matching inside "12.5".
DOSE = r'(?<![\d.])(2\.5|5(?:\.0)?|7\.5|10(?:\.0)?|12\.5|15(?:\.0)?)(?![\d.])'
FWD = re.compile(DOSE + r'\s*(?:mg|milligrams?)\b[^\u00a3]{0,160}?\u00a3\s?(\d{1,3}(?:[.,]\d{2})?)', re.I)
REV = re.compile(r'\u00a3\s?(\d{1,3}(?:[.,]\d{2})?)[^\u00a3]{0,110}?' + DOSE + r'\s*(?:mg|milligrams?)\b', re.I)


def norm_dose(raw: str) -> str:
    return f'{float(raw):g}'


def to_text(markup: str) -> str:
    markup = re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>', ' ', markup)
    markup = re.sub(r'(?s)<[^>]+>', '\n', markup)
    markup = html_mod.unescape(markup)
    return re.sub(r'[ \t\r\f\v]+', ' ', markup)


def extract(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for m in FWD.finditer(text):
        found.setdefault(norm_dose(m.group(1)), float(m.group(2).replace(',', '.')))
    for m in REV.finditer(text):
        found.setdefault(norm_dose(m.group(2)), float(m.group(1).replace(',', '.')))
    return {d: p for d, p in found.items() if 60 <= p <= 500}


def fetch(url: str) -> str:
    req = Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-GB,en;q=0.9',
    })
    with urlopen(req, timeout=25) as r:
        raw = r.read()
    charset = 'utf-8'
    ctype = r.headers.get('Content-Type', '')
    if 'charset=' in ctype:
        charset = ctype.split('charset=')[-1].split(';')[0].strip()
    try:
        return raw.decode(charset, 'replace')
    except LookupError:
        return raw.decode('utf-8', 'replace')


def best_for(urls: list[str]) -> tuple[dict[str, float], str]:
    best: tuple[dict[str, float], str] = ({}, '')
    for url in urls:
        try:
            markup = fetch(url)
        except (HTTPError, URLError, TimeoutError, OSError):
            continue
        found = extract(to_text(markup))
        if len(found) > len(best[0]):
            best = (found, url)
        if len(found) >= 6:
            break
    return best


def plausible(prices: dict[str, float]) -> dict[str, float]:
    """Drop doses whose price collapses relative to a cheaper, lower dose.

    Published pen prices rise with dose. A "15mg" reading cheaper than the 7.5mg on
    the same page is a mis-match: a per-injection figure, a different product, or a
    promotional block the pattern walked into. Flat pricing passes; collapse does not.
    """
    kept: dict[str, float] = {}
    prev = 0.0
    for dose in DOSE_VALUES:
        price = prices.get(dose)
        if price is None:
            continue
        if prev and price < prev * 0.85:
            continue
        kept[dose] = price
        prev = price
    return kept


def candidate_urls(p: dict) -> list[str]:
    urls = []
    if p.get('source_url'):
        urls.append(p['source_url'])
    domain = p.get('domain') or ''
    if domain:
        for path in ('/mounjaro', '/weight-loss', '/weight-loss/mounjaro'):
            u = f'https://{domain}{path}'
            if u not in urls:
                urls.append(u)
    return urls[:4]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='merge improvements into the index')
    ap.add_argument('--max-doses', type=int, default=5, help='re-read providers below this dose count')
    ap.add_argument('--workers', type=int, default=5)
    args = ap.parse_args()

    data = json.loads(INDEX.read_text())
    providers = data['providers']
    targets = [p for p in providers if len(p.get('prices_gbp') or {}) <= args.max_doses - 1]
    print(f'{len(providers)} providers, {len(targets)} with fewer than {args.max_doses} doses')

    improved, unchanged, failed = [], 0, []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(best_for, candidate_urls(p)): p for p in targets}
        for i, fut in enumerate(as_completed(futs), 1):
            p = futs[fut]
            try:
                found, url = fut.result()
            except Exception as exc:                                  # noqa: BLE001
                failed.append((p['provider'], str(exc)[:60]))
                found, url = {}, ''
            before = len(p.get('prices_gbp') or {})
            existing = dict(p.get('prices_gbp') or {})
            # Add-only merge. A verified price already in the index outranks anything
            # this pass reads: the earlier crawl read that exact page, and a second
            # pass that disagrees is more likely to have mis-paired than to be right.
            merged = dict(existing)
            ceiling = 0.0
            for dose in DOSE_VALUES:
                if dose in merged:
                    ceiling = max(ceiling, merged[dose])
                    continue
                cand = found.get(dose)
                if cand is None:
                    continue
                # Same rule ci_check enforces: a higher dose never costs less than a
                # lower one. A candidate that breaks it is a mis-pair, not a bargain.
                if cand < ceiling:
                    continue
                merged[dose] = cand
                ceiling = cand
            if len(merged) > before:
                print(f'  [{i:>2}/{len(targets)}] {p["provider"][:26]:<26} {before} → {len(merged)} doses')
                if args.write:
                    p['prices_gbp'] = {d: merged[d] for d in DOSE_VALUES if d in merged}
                    p['source_url'] = url or p.get('source_url', '')
                    p['retrieved_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
                    p['doses_found'] = len(p['prices_gbp'])
                    p['checks'] = len(p['prices_gbp'])
                    p['confidence'] = 'high' if len(p['prices_gbp']) >= 4 else 'medium'
                improved.append({'provider': p['provider'], 'before': before,
                                 'after': len(merged), 'url': url, 'found': found})
            else:
                unchanged += 1
                print(f'  [{i:>2}/{len(targets)}] {p["provider"][:26]:<26} no change ({before} doses, found {len(found)})')
            time.sleep(0.2)

    print(f'\nimproved {len(improved)}, unchanged {unchanged}, errors {len(failed)}')
    if failed:
        print('  errors:', failed[:6])

    REPORT_DIR.mkdir(exist_ok=True)
    report = REPORT_DIR / f'recrawl-{datetime.now(timezone.utc):%Y-%m-%d}.json'
    report.write_text(json.dumps({'improved': improved, 'failed': failed},
                                 indent=1, ensure_ascii=False))
    print('report:', report.relative_to(ROOT))

    if args.write and improved:
        data['generated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        INDEX.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        counts = {d: sum(1 for p in providers if d in (p.get('prices_gbp') or {})) for d in DOSE_VALUES}
        print('coverage now:', ', '.join(f'{d}mg={n}' for d, n in counts.items()))
    elif not args.write:
        print('(dry run — pass --write to merge)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
