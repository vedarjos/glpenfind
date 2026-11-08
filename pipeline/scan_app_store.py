"""Scan the UK App Store for anything resembling a price index, and record it.

Written because a direct competitor (GLP1 Offers — Price Tracker) went unnoticed
for weeks: the earlier research was scoped to one named rival and to trademark
risk, and never searched the category itself. Run this before any pricing or
positioning decision, and again monthly.

Usage:
    python3 pipeline/scan_app_store.py            # scan + write report
    python3 pipeline/scan_app_store.py --terms a,b
"""
import argparse
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

REPORTS = Path('reports')
TERMS = [
    'mounjaro', 'mounjaro price', 'mounjaro cost', 'glp1 offers', 'glp-1',
    'wegovy', 'ozempic', 'weight loss injections', 'weight loss pen prices',
    'cheapest pharmacy', 'pharmacy compare', 'prescription price',
]
# words that mark an app as competing with a price index rather than a tracker
RIVAL_WORDS = ('price', 'cheap', 'compare', 'cost', 'offer')
COUNTRY = 'gb'


def search(term):
    q = urllib.parse.urlencode({'term': term, 'country': COUNTRY,
                                'entity': 'software', 'limit': 50})
    url = f'https://itunes.apple.com/search?{q}'
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return json.load(r)['results']
    except Exception as e:
        print(f'  ! {term}: {e}')
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--terms', help='comma-separated override')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    terms = [t.strip() for t in args.terms.split(',')] if args.terms else TERMS

    apps = {}
    for t in terms:
        for a in search(t):
            apps.setdefault(a['trackId'], a)

    rivals = []
    for a in apps.values():
        blob = (a['trackName'] + ' ' + (a.get('description') or '')).lower()
        if any(w in a['trackName'].lower() for w in RIVAL_WORDS) and \
           any(k in blob for k in ('glp', 'mounjaro', 'wegovy', 'ozempic', 'weight loss', 'pharmacy')):
            rivals.append(a)
    rivals.sort(key=lambda a: -a.get('userRatingCount', 0))

    print(f'{len(apps)} unique apps across {len(terms)} terms · {len(rivals)} price/compare rivals')
    for a in rivals:
        paid = a.get('formattedPrice', 'Free')
        print(f"  {paid:<7} ★{a.get('averageUserRating', 0):.1f} "
              f"({a.get('userRatingCount', 0):>6,})  {a['trackName'][:44]:<44} "
              f"upd {a.get('currentVersionReleaseDate', '')[:10]}  {a.get('sellerName', '')[:28]}")

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f'app-store-scan-{date.today().isoformat()}.json'
    out.write_text(json.dumps({
        'scanned': date.today().isoformat(),
        'country': COUNTRY,
        'terms': terms,
        'unique_apps': len(apps),
        'rivals': [{
            'name': a['trackName'], 'seller': a.get('sellerName'),
            'price': a.get('formattedPrice'), 'rating': a.get('averageUserRating'),
            'ratings': a.get('userRatingCount'), 'released': a.get('releaseDate', '')[:10],
            'updated': a.get('currentVersionReleaseDate', '')[:10],
            'url': a.get('trackViewUrl'),
        } for a in rivals],
    }, indent=1))
    print(f'\nwritten: {out}')


if __name__ == '__main__':
    main()
