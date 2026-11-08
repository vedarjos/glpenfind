# App Store submission — what is done, what is gated

Checked against Apple's own references on 30 Oct 2026. Prices/specs change; re-verify
before uploading.

## Assets: done and sized correctly

| Asset | Spec | State |
|---|---|---|
| App icon | 1024×1024, **no alpha**, no rounded corners (iOS masks it) | `assets/icon-1024.png`, installed at `ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png` |
| Web icons | 180 / 192 / 512 | `www/apple-touch-icon.png`, `www/icon-192.png`, `www/icon-512.png` |
| Screenshots | **1179×2556** (iPhone with Dynamic Island, medium display) — Apple requires at least one, allows up to 10 | `store/screenshots/01..03` — verified 1179×2556, no alpha |
| Splash | matches the app field `#A7D4E4` | `capacitor.config.ts` |

Larger 6.9" screenshots (1320×2868 or 1290×2796) are optional: if absent, App Store
Connect scales the 1179×2556 set. Uploading 6.9" explicitly is only worth it when the
layout changes noticeably at that width.

Icon rationale: one glyph, cream `£` on oxblood `#82241F`. A three-bar chart was tried
first and rejected — three ideas competing, unreadable at 40px. The single glyph holds
at 40px and the oxblood tile out-contrasts a pale-blue one on a home screen full of
blue icons.

## Gated — cannot be done without you

1. **Xcode.** Only Command Line Tools are installed (`xcode-select -p` →
   `/Library/Developer/CommandLineTools`), so there is no simulator and no archive.
   Needs Xcode.app, then `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`.
2. **Apple Developer Program** membership (App Store Connect access, APNs key).
3. **Privacy policy URL** — the page is written (`www/privacy.html`, linked from the app
   footer and serving 9 sections); it needs a public URL. Any static host works.

## Policy gates on the product itself

- **4.2 minimum functionality.** A webview that only renders `www/` is the classic
  rejection. Ship one genuinely native capability first. Cheapest credible one here:
  local notification when a tracked pharmacy's price drops, via
  `@capacitor/push-notifications` (or local notifications, no APNs key needed to start).
  Say which in the review notes.
- **Trademark in the title.** "Mounjaro" is Novo Nordisk's. An app name implying
  affiliation gets rejected; keep the brand word out of the title, and state
  non-affiliation in the description.
- **Health data (5.1.3).** The app shows prescription pricing. Needs: explicit purpose
  string in the description, App Privacy answers declaring no data collected (true today
  — everything is bundled JSON), and if personal data is ever stored, an in-app consent
  screen and deletion path.
- **`PrivacyInfo.xcprivacy`** — done: `ios/App/App/PrivacyInfo.xcprivacy` declares no
  tracking, no collected data and no required-reason APIs, which is true of the app today.
  Update it the moment anything is collected.
- **Export compliance** — done: `ITSAppUsesNonExemptEncryption = false` in `Info.plist`, so
  uploads stop asking the encryption question.
- **Age rating.** Medical/treatment information lands at 12+; answer the questionnaire
  honestly rather than defaulting to 4+.

## Listing copy (draft)

- **Name** (30 chars): `Dose Price Index` — avoids the drug-brand gate
- **Subtitle** (30): `UK pharmacy prices, compared`
- **Keywords** (100): `mounjaro,weight loss,pharmacy,price,compare,uk,jab,pen,dose,cheapest`
- **Description opener**: what it does, who it is for, and one line of non-affiliation:
  "Independent price index. Not affiliated with any pharmacy or manufacturer."

## Order of work

1. Xcode + developer account (yours) → then `npx cap sync ios` and archive.
2. Native capability for 4.2 — price-drop notification.
3. Privacy policy page + `PrivacyInfo.xcprivacy`.
4. TestFlight internal build → install on your own phone → fix what breaks.
5. Listing copy, screenshots, age rating, App Privacy answers.
6. Submit.
