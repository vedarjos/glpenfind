"""Build a self-contained public website from the private repo, and optionally
publish it to a standalone git checkout.

Root of the published site is the marketing page, not the app home — the site is
the advert, and the app pages sit beside it. Everything is rewritten to work from
a flat root so GitHub Pages needs no configuration.

The published site lives in its OWN repository, outside this working tree. An
earlier version of this script wrote into ./dist and wiped it on every run, which
deleted the nested .git and silently made later commits land in the private repo.
Never keep a repo inside a build directory.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

WWW = Path('www')
SITE = WWW / 'site'
DIST = Path('dist')
PUBLISH_DIR = Path.home() / 'sites' / 'glpenfind-public'

APP_FILES = ['app.js', 'styles.css', 'icon-192.png', 'icon-512.png',
             'apple-touch-icon.png', 'manifest.webmanifest']
APP_PAGES = ['prices.html', 'pharmacies.html', 'privacy.html']


def reset():
    """Empty dist/ but never touch a .git inside it."""
    if DIST.exists():
        for item in DIST.iterdir():
            if item.name == '.git':
                continue
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    else:
        DIST.mkdir()
    (DIST / '.nojekyll').write_text('')          # stop GitHub Pages running Jekyll


def rewrite(html: str) -> str:
    """Turn ../x into x now that the marketing pages sit at the root."""
    return re.sub(r'(href|src)="\.\./([^"]+)"', r'\1="\2"', html)


def build():
    reset()

    # 1. marketing pages become the site root, advert included
    for page in SITE.glob('*.html'):
        (DIST / page.name).write_text(rewrite(page.read_text()))

    # 2. its stylesheet and images
    shutil.copy2(SITE / 'site.css', DIST / 'site.css')
    shutil.copytree(SITE / 'img', DIST / 'img')

    # 3. the app pages, reachable from the advert
    for page in APP_PAGES:
        shutil.copy2(WWW / page, DIST / page)
    for f in APP_FILES:
        if (WWW / f).exists():
            shutil.copy2(WWW / f, DIST / f)

    # 4. data and icon set
    shutil.copytree(WWW / 'data', DIST / 'data')
    if (WWW / 'icons').exists():
        shutil.copytree(WWW / 'icons', DIST / 'icons')

    # 5. keep /site/ working for links already shared
    (DIST / 'site').mkdir()
    (DIST / 'site' / 'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=/">'
        '<title>GLPenFind</title><a href="/">GLPenFind</a>')

    print('built dist/:', sum(1 for _ in DIST.rglob('*') if _.is_file()), 'files')


def publish(message='publish site'):
    """Sync dist/ into the standalone site repo, commit, push."""
    if not (PUBLISH_DIR / '.git').exists():
        sys.exit(f'no git repo at {PUBLISH_DIR} — run: '
                 f'mkdir -p {PUBLISH_DIR} && git -C {PUBLISH_DIR} init -b main')

    subprocess.run(['rsync', '-a', '--delete', '--exclude', '.git',
                    f'{DIST}/', f'{PUBLISH_DIR}/'], check=True)
    subprocess.run(['git', '-C', str(PUBLISH_DIR), 'add', '-A'], check=True)

    changed = subprocess.run(['git', '-C', str(PUBLISH_DIR), 'status', '--porcelain'],
                             capture_output=True, text=True).stdout.strip()
    if changed:
        subprocess.run(['git', '-C', str(PUBLISH_DIR), 'commit', '-q', '-m', message], check=True)
        print('committed:', changed.count(chr(10)) + 1, 'changed paths')

    subprocess.run(['git', '-C', str(PUBLISH_DIR), 'push', '-q', 'origin', 'main'], check=True)
    head = subprocess.run(['git', '-C', str(PUBLISH_DIR), 'rev-parse', '--short', 'HEAD'],
                          capture_output=True, text=True).stdout.strip()
    url = subprocess.run(['git', '-C', str(PUBLISH_DIR), 'remote', 'get-url', 'origin'],
                         capture_output=True, text=True).stdout.strip()
    print(f'pushed {head} → {url}')


if __name__ == '__main__':
    build()
    if '--publish' in sys.argv:
        words = [a for a in sys.argv[1:] if not a.startswith('--')]
        publish(' '.join(words) or 'publish site')
