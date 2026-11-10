# GLPenFind — UK weight-loss pen price index

An independent price index for weight-loss pens in the UK: every pharmacy we can
verify, ranked by what you actually pay — **and by how much they make you prove
before they'll tell you**.

Built on the research, scoring model and evidence rules of
[`ljubomirj/mounjaro-find-uk`](https://github.com/ljubomirj/mounjaro-find-uk).

**Live site:** https://vedarjos.github.io/
**Stable privacy URL:** https://vedarjos.github.io/privacy.html

- **Web app:** `www/`
- **Marketing site:** `www/site/`
- **iOS shell:** `ios/` (Capacitor)

## The idea

Prices for the same pen vary by more than £100 a month across UK pharmacies, and
half of them won't show you a number until you've finished a consultation. Two
pharmacies can quote the same figure and feel nothing alike to use.

So every pharmacy carries **two** numbers:

1. **Price** — read from the pharmacy's own page, with the exact URL and time.
2. **Ease** — a penalty score built from what the pharmacy itself says it will ask
   of you before quoting.

No pharmacy can buy a position. There is no affiliate parameter on any outbound
link.

## Status

Data snapshot: **30 October 2026**.

| Piece | State |
|---|---|
| Pharmacies with a published price | **68** |
| Publishing 4+ of the 6 dose strengths | 44 |
| Listed but unpriced (behind a consultation, no price published, or unreadable) | **13** — 6 gated, 5 no price, 2 blocked |
| Removed for compliance / register failures | **4** |
| GPhC register audit | **80 checked, 79 verified** against a numbered premises; 1 demoted when its number turned out to belong to another pharmacy |
| Trustpilot ratings | 71 domains |
| Ordering-step profiles | 83 providers |
| iOS build | **Blocked — no `Xcode.app` on this machine** (Command Line Tools cannot archive) |
| App Store submission | Not started — needs the Apple Developer Program, a stable privacy URL, and one native capability for guideline 4.2 |

## Compliance is structural, not copy

Home page must not name a prescription-only medicine or show a price (MHRA Blue
Guide, Appendix 6). That constraint shapes the whole information architecture:

| Page | Contains |
|---|---|
| `www/index.html` | Counts only. No POM name, no £ figure — verified programmatically |
| `www/prices.html` | The factual price list, per dose, with source links |
| `www/pharmacies.html` | Directory with GPhC register links |
| `www/site/` | Marketing site: what the app does, method, support |
| `www/privacy.html` | Policy: no account, no analytics, no tracking |

Discount and offer badges were **removed** from the price list: highlighting a
special offer on a POM price is what the guidance prohibits.

The brand name lives only in the App Store keyword field, which is indexed but
never displayed.

## Where the data comes from

No aggregator's database is copied. Each price is read from the pharmacy's own
page by a headless-Chromium crawler, and every row stores:

- `source_url` — the exact page the price came from
- `retrieved_at` — when it was read
- `confidence` — `medium` when the page yielded fewer than four doses

Two rules keep the numbers honest:

- **A price must never fall as the dose rises.** If 12.5mg reads cheaper than
  7.5mg, something was misread; the single worst row is dropped and the record
  is marked `medium` rather than published as fact.
- **Never read a pharmacy's own "price comparison" article as its price.** Those
  URLs are blocklisted — they're marketing, not a price.

## Layout

```
mounjaro-find-uk-ios/
├── www/                     # the app (source of truth)
│   ├── index.html           # compliance-safe home: counts only
│   ├── prices.html          # the factual price list
│   ├── pharmacies.html      # generated directory with register links
│   ├── privacy.html
│   ├── site/                # marketing site: home, method, support
│   ├── app.js               # ranking, dose switcher, Ease badges
│   ├── styles.css
│   └── data/
│       ├── price-index.json # generated
│       ├── gphc.json        # register audit
│       ├── ordering.json    # Ease profiles
│       └── ratings.json
├── ios/App/                 # Capacitor shell, icons, PrivacyInfo.xcprivacy
├── pipeline/                # crawlers, verifiers, generators
├── store/                   # App Store screenshots and share card
├── docs/                    # submission notes, ASO, naming, CV entry
├── reports/                 # audit outputs
└── screenshots/             # QA captures
```

## Publishing the site

The public site is built from `www/` into a flat `dist/` and pushed to a separate
public repo, because GitHub Pages needs a public repository on a free plan:

```bash
python3 pipeline/build_public_site.py --publish "what changed"   # build + commit + push
```

The published checkout is `~/sites/glpenfind-public` (its own repo, remote
`vedarjos/vedarjos.github.io`), so the site lives at the bare user domain rather
than a project subpath. Keep it outside this working tree: an earlier version
built into `./dist` and wiped the nested `.git` on every run, which silently sent
later commits into the private repo.

`python3 pipeline/ci_check.py` runs on every push (`.github/workflows/validate.yml`)
and fails the build on: a price that falls as the dose rises, a provider with no
source URL or retrieval date, a pharmacy listed as both removed and unread, a
home page that names a prescription-only medicine or shows a price, or a privacy
manifest that exists on disk but is not registered in the Xcode project.

## Run it

```bash
npm run serve          # http://localhost:8790
```

## Rebuild the data

```bash
python3 pipeline/finalize_data.py     # price index
python3 pipeline/fetch_ratings.py     # Trustpilot
python3 pipeline/build_ordering.py    # Ease profiles
python3 pipeline/verify_regulation.py # GPhC audit
```

Hand-verified steps live in `pipeline/manual_steps.json` so a rebuild cannot wipe
them.

## Ship to iOS

Xcode is required — Command Line Tools alone cannot build or archive.

```bash
npm install
npm run ios:sync     # copies www/ into the bundle, then strips cache-busters
npm run ios:build    # simulator build, no signing needed
npm run ios:open     # set Team, then Run on a device
```

**Never ship `?v=` query strings into the iOS bundle.** `styles.css?v=21` is right for
GitHub Pages, but inside the Capacitor WebView a query string on a local asset 404s and the
page renders with no CSS at all — a blank white screen, no error, nothing in the log. The
binary is versioned, so the app never needs cache busting; `pipeline/strip_cachebusters.py`
runs automatically as part of `ios:sync` and leaves `www/` untouched.

- Bundle id: `uk.whimsical.glpenfind`
- Version: `1.0 (1)`
- `ITSAppUsesNonExemptEncryption = false` — declared, no non-exempt crypto
- `PrivacyInfo.xcprivacy` — no tracking, no collected data; required-reason APIs
  `CA92.1` and `C617.1`; **registered in the Resources build phase**, without
  which it silently would not ship

## Ship to Android / F-Droid

Android needs a JDK and the Android SDK; neither ships with macOS.

```bash
npm run android:sync     # copies www/ into the bundle, then strips cache-busters
npm run android:build    # ./gradlew assembleDebug
```

Toolchain used for the first build (no root required, nothing installed system-wide):

```bash
# JDK 21 — Homebrew's openjdk formula collided with fontconfig on this machine,
# so the Temurin tarball is unpacked under ~/jdk instead
curl -fL -o temurin21.tar.gz https://api.adoptium.net/v3/binary/latest/21/ga/mac/aarch64/jdk/hotspot/normal/eclipse
tar xzf temurin21.tar.gz -C ~/jdk
export JAVA_HOME="$HOME/jdk/jdk-21.0.13+9/Contents/Home"
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"
```

- Application id: `uk.whimsical.glpenfind` (same as the iOS bundle id)
- `versionCode 1` / `versionName "1.0"` — F-Droid reads these from the manifest,
  and a release tag must match them
- `minSdk 24`, `compileSdk 36`, `targetSdk 36`
- Icons and splash: `assets/icon.png` (1024², logo flattened onto the sky field)
  through `npx capacitor-assets generate --android`

## Native surface: the home-screen widget

Android ships a widget (`android/app/src/main/java/.../PriceWidgetProvider.java`) that
shows the cheapest published price at the dose the user picks, plus how many pharmacies
publish that dose and the date it was read. It parses `assets/public/data/price-index.json`
itself in Java — no WebView, no network, no account — which is what distinguishes it from
a browser tab. `WidgetConfigActivity` picks the dose per widget instance; the choice is
stored per `appWidgetId`, so two widgets can watch different doses.

Also native: launcher shortcuts (`res/xml/shortcuts.xml`) that open the price list or the
directory directly, via a validated `route` extra in `MainActivity`.

Widget layout, palette and strings live in `res/layout/widget_price.xml`,
`res/values/colors.xml` and `res/values/strings.xml`. The picker preview image is
`res/drawable-nodpi/widget_preview.png`; `previewLayout` covers API 31+.

This is the answer to F-Droid's Inclusion Policy §Quality Control 3 and Apple's guideline
4.2 ("apps should provide native features and enhancements when they wrap a website").
The iOS counterpart — a WidgetKit extension — is not built yet.

**F-Droid submission is blocked on three things that are not code:**

1. ~~Source repo private~~ — published as https://github.com/vedarjos/glpenfind.
2. ~~No licence file~~ — GPL-3.0-or-later, `LICENSE` at the root of both repos.
3. ~~No native features~~ — home-screen widget and launcher shortcuts, above.

What remains is time, not code: Inclusion Policy §Quality Control 6 asks for three months
of active development, and the first commit is 20 October 2026.

Metadata F-Droid reads lives in `fastlane/metadata/android/en-GB/` (title,
short and full description, changelog, icon, phone screenshots).

## Store gates before submission

- **Apple 4.2 Minimum Functionality** — a bare webview gets rejected. Needs one
  native capability: a price-change notification, or camera capture for reports.
- **Stable privacy URL** — a quick tunnel is not acceptable; needs a real domain.
- **Health data** — nothing stores weight, dose history or photos today. Adding
  user reports with photos brings 5.1.3, consent, and a deletion path.

## Rules the app never breaks

- No price without a source URL and a retrieval date.
- Never submit a medical consultation on a user's behalf.
- Never list a pharmacy we cannot tie to a registered premises.
- No "you qualify" language: the app reports prices and stated criteria; a
  prescriber decides eligibility.

## Source repositories

- **Private working repo** (this one): notes, crawl artefacts, store assets, reports.
- **Public app repo**: https://github.com/vedarjos/glpenfind — the mirror F-Droid
  builds from. Contains `www/`, `pipeline/`, `android/`, `ios/`, `fastlane/` and the
  F-Droid recipe; excludes crawl artefacts, screenshots and working notes.

Releases are cut by re-exporting the app paths into the mirror and tagging there:

```bash
git archive HEAD -- www pipeline android ios fastlane docs .gitignore LICENSE README.md \
  capacitor.config.ts package.json package-lock.json | tar -x -C /tmp/mirror
# then, in the mirror: git commit, git tag -a v1.1, git push --tags
```

## Licence

GLPenFind is released under the **GNU General Public License v3.0 or later**
(`GPL-3.0-or-later`) — see `LICENSE`. You may run, study, share and modify it, and
any distributed derivative must stay under the same terms.

The price data is not part of the licence grant: it is read from each pharmacy's own
published page, and every record keeps its source URL and read date.
