"""Guard rails for the data and the compliance split.

Runs in CI on every push. Fails loudly rather than letting a bad rebuild reach
the price list: these are the exact faults this project has hit before.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / 'www'
DOSE_ORDER = ['2.5', '5', '7.5', '10', '12.5', '15']
POM = re.compile(r'mounjaro|tirzepatide|wegovy|ozempic', re.I)
PRICE = re.compile(r'£\s?\d')

failures: list[str] = []
notes: list[str] = []


def fail(msg):
    failures.append(msg)


def check_json():
    for name in ('price-index', 'gphc', 'ordering', 'ratings'):
        p = WWW / 'data' / f'{name}.json'
        try:
            json.loads(p.read_text())
        except Exception as e:
            fail(f'{p.name} is not valid JSON: {e}')


def check_provenance():
    d = json.loads((WWW / 'data' / 'price-index.json').read_text())
    for prov in d['providers']:
        if not prov.get('source_url'):
            fail(f"{prov['provider']}: no source_url")
        elif not str(prov['source_url']).startswith('https://'):
            fail(f"{prov['provider']}: malformed source_url {prov['source_url']}")
        if not prov.get('retrieved_at'):
            fail(f"{prov['provider']}: no retrieved_at")


def check_monotonic():
    """A price must never fall as the dose rises."""
    d = json.loads((WWW / 'data' / 'price-index.json').read_text())
    for prov in d['providers']:
        seen = [(k, v) for k, v in (prov.get('prices_gbp') or {}).items() if v]
        seen.sort(key=lambda kv: DOSE_ORDER.index(kv[0]))
        for (d1, p1), (d2, p2) in zip(seen, seen[1:]):
            if p2 < p1 - 0.005:
                fail(f"{prov['provider']}: {d2}mg £{p2} is below {d1}mg £{p1}")


def check_lists_disjoint():
    d = json.loads((WWW / 'data' / 'price-index.json').read_text())
    removed = set(d.get('removed_for_compliance') or [])
    overlap = removed & {u['provider'] for u in d.get('unread') or []}
    if overlap:
        fail(f"listed as both removed and unread: {sorted(overlap)}")


def check_home_compliance():
    """The home page must not name a POM or show a price (MHRA App. 6)."""
    for page in (WWW / 'index.html', WWW / 'site' / 'index.html'):
        if not page.exists():
            continue
        text = page.read_text()
        # strip tags so we only judge visible copy
        visible = re.sub(r'<[^>]+>', ' ', text)
        if POM.search(visible):
            fail(f'{page.relative_to(ROOT)} names a POM on a home page')
        if PRICE.search(visible):
            fail(f'{page.relative_to(ROOT)} shows a price on a home page')


def check_manifest_registered():
    pbx = ROOT / 'ios' / 'App' / 'App.xcodeproj' / 'project.pbxproj'
    manifest = ROOT / 'ios' / 'App' / 'App' / 'PrivacyInfo.xcprivacy'
    if not manifest.exists():
        fail('PrivacyInfo.xcprivacy is missing')
        return
    text = pbx.read_text()
    if 'PrivacyInfo.xcprivacy' not in text:
        fail('PrivacyInfo.xcprivacy exists but is not registered in project.pbxproj')
    if text.count('PrivacyInfo.xcprivacy') < 3:
        fail('PrivacyInfo.xcprivacy is referenced but not in the Resources build phase')


def check_duplicates():
    d = json.loads((WWW / 'data' / 'price-index.json').read_text())
    names = [p['provider'] for p in d['providers']]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        fail(f'duplicate providers: {sorted(dupes)}')
    notes.append(f"{len(names)} providers, {sum(1 for p in d['providers'] if len([v for v in (p.get('prices_gbp') or {}).values() if v]) >= 4)} with 4+ doses")


def main():
    check_json()
    if not failures:
        check_provenance()
        check_monotonic()
        check_lists_disjoint()
        check_duplicates()
    check_home_compliance()
    check_manifest_registered()

    for n in notes:
        print(f'· {n}')
    if failures:
        print(f'\n✗ {len(failures)} problem(s):')
        for f in failures:
            print('  -', f)
        sys.exit(1)
    print('\n✓ all checks passed')


if __name__ == '__main__':
    main()
