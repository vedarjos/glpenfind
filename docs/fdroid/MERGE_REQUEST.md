# New app: GLPenFind (uk.whimsical.glpenfind)

## What it is

An independent index of what UK pharmacies publish for a private weight-management
consultation, per pen, at every dose. Every pharmacy is checked against the General
Pharmaceutical Council register of pharmacy premises; each price is read from that
pharmacy's own page and stored with the source URL and the date it was read.

Price is ranked lowest first. "Ease" is built from what each pharmacy says it will ask
of you before a prescriber decides — questionnaire, photos, video call, ID, GP records,
stated turnaround. Where a pharmacy hides its price behind a consultation, the app says
so rather than guessing.

No accounts, no tracking, no advertising, no analytics, no third-party SDKs. The index
ships inside the APK and works offline.

## Compliance

- **Licence:** GPL-3.0-or-later, `LICENSE` at the repo root.
- **Source:** https://github.com/vedarjos/glpenfind — public, tag `v1.1` matches
  `versionName 1.1` / `versionCode 2`.
- **Dependencies:** Capacitor 8 (MIT) and its Android/iOS platform packages only.
  No Play Services, no Firebase, no Crashlytics, no ad or analytics SDK.
- **Permissions:** `INTERNET` only, and only to load the bundled WebView origin
  (`https://localhost`). The app makes no network calls of its own.
- **Backup:** `android:allowBackup="false"` — the app stores nothing, so there is
  nothing to back up.
- **Metadata:** `fastlane/metadata/android/en-GB/` (title, descriptions, changelog,
  icon, two phone screenshots).

## Build notes for reviewers

It is a Capacitor app, so the web assets are generated into the Android project at
build time rather than committed:

```bash
npm ci
npx cap sync android                      # copies www/ → android/app/src/main/assets/public
python3 pipeline/strip_cachebusters.py    # see below
cd android && ./gradlew assembleRelease
```

**The `strip_cachebusters.py` step is required, not optional.** The site ships
cache-busted asset URLs (`styles.css?v=22`) because it is also published on GitHub
Pages, where a stale stylesheet is otherwise invisible. Inside the Capacitor WebView a
query string on a local asset can 404, and the app then renders a blank white screen
with no error in the log. The script removes `?v=` from the bundled copy only, leaving
`www/` untouched. It runs on iOS and Android bundles alike and exits non-zero if any
`?v=` survives.

No proprietary toolchain: JDK 17+ and the Android SDK are sufficient. Locally verified
with Temurin 21, `compileSdk 36`, AGP from the Gradle wrapper in the repo.

## Verification

- `./gradlew assembleDebug` and `assembleRelease` both succeed from a clean clone.
- Installed on an Android 16 (API 36) emulator: home page, price list, dose switching
  and sorting all render; no blank screen.
- Version in the built APK: `uk.whimsical.glpenfind`, `versionCode 1`, `versionName 1.0`.

## Native features (Inclusion Policy, Quality Control 3)

The app is a WebView shell, so this is the clause that matters. It ships native
surfaces that do not exist in a browser:

- **Home-screen widget** (`PriceWidgetProvider`, `AppWidgetProvider`). Shows the cheapest
  published price at the dose the user picked, the pharmacy name, how many pharmacies
  publish that dose and the date the price was read. It parses the index from the APK's
  asset bundle (`public/data/price-index.json`) in native Java — no WebView, no network,
  no account. Tapping it opens the app; the ↻ glyph re-reads the bundle.
- **Widget configuration activity** (`WidgetConfigActivity`) — dose chosen per widget
  instance and stored per `appWidgetId`, so two widgets can watch different doses.
- **Launcher shortcuts** (`res/xml/shortcuts.xml`) — "Prices" and "Pharmacies" open the
  WebView directly on that page via a validated `route` extra in `MainActivity`.

Verified on an Android 16 (API 36) emulator: widget placed via the launcher picker,
dose selected, correct price rendered from the bundle (£145 / Farmeci / cheapest of 52 at
7.5mg; £98.99 / IQ Doctor / cheapest of 65 at 2.5mg).

The WebView still renders the price list and directory; the widget and shortcuts are the
native layer on top of it.
