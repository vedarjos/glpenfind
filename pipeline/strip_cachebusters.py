"""Strip cache-buster query strings from the bundled web assets, on every platform.

Why this exists: `styles.css?v=21` is essential on GitHub Pages (a stale stylesheet
is invisible to the user and painful to diagnose), but inside the Capacitor WebView
a query string on a local asset can 404. iOS then renders the page with no CSS at
all — a blank white screen with no error in the console or the device log. Android
runs the same assets through `https://localhost` and gets the same treatment for the
same reason. The binary is versioned, so the app never needs cache busting; strip it
after every `cap sync` and leave `www/` alone so the site keeps its busting.

Run automatically by `npm run ios:sync` and `npm run android:sync`.
"""
import re
import sys
from pathlib import Path

BUNDLES = [
    Path('ios/App/App/public'),                    # iOS: capacitor://localhost
    Path('android/app/src/main/assets/public'),    # Android: https://localhost
]
PATTERN = re.compile(r'(src|href)="([^"?]+)\?v=\d+"')


def strip(bundle: Path) -> int:
    """Strip one bundle. Returns the number of references removed, or -1 if absent."""
    if not bundle.exists():
        return -1

    changed = 0
    for page in bundle.rglob('*.html'):
        text = page.read_text()
        stripped, n = PATTERN.subn(r'\1="\2"', text)
        if n:
            page.write_text(stripped)
            changed += n
            print(f'  {page.relative_to(bundle)}: {n} reference(s)')
    return changed


def main() -> int:
    total = 0
    seen = 0
    failed = False

    for bundle in BUNDLES:
        if not bundle.exists():
            print(f'skipping {bundle} (not present — run `npx cap sync` for that platform)')
            continue
        seen += 1
        changed = strip(bundle)
        total += max(changed, 0)
        state = f'{changed} reference(s)' if changed else 'already clean'
        print(f'{bundle}: {state}')

        leftover = [str(p.relative_to(bundle)) for p in bundle.rglob('*.html')
                    if re.search(r'\?v=\d+', p.read_text())]
        if leftover:
            print(f'  still carrying ?v= in: {leftover}', file=sys.stderr)
            failed = True

    if not seen:
        print('no bundles found — nothing to do', file=sys.stderr)
        return 1
    print(f'total stripped: {total}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
