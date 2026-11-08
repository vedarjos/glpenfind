# CV entry — GLPenFind

Three formats. All figures below are verified in this repo; none are estimates.

---

## 1. Short form (2–3 bullets, for a CV under "Projects")

**GLPenFind — UK prescription weight-management price index** · Founder & builder · 2026

- Built a price index covering **68 UK pharmacies across 6 dose strengths**, sourced by crawling each pharmacy's own product pages rather than licensing third-party data — every figure carries its source URL and retrieval date.
- Audited all **87 candidate pharmacies against the GPhC register of pharmacy premises**, removing 4 that could not be verified and resolving 6 more through registration numbers published on their own sites.
- Restructured the product for MHRA compliance after reading Blue Guide Appendix 6: medicine names and prices removed from the home screen, price data moved to a factual list page, and all discount-code and offer UI deleted.
- Shipped a Capacitor iOS build with a privacy manifest, export-compliance declaration and complete App Store metadata (name, subtitle, 100-character keyword field, description).

---

## 2. Detailed form (for a portfolio page or a "Selected projects" section)

**GLPenFind** — a comparison app for UK prescription weight-management pens

The UK market for these medicines is opaque: dozens of registered pharmacies, prices that vary by more than £1,600 a year at the same dose, and no way to compare what each one makes you do before you can buy.

I built the data layer, the compliance model, the interface and the iOS package.

**Data.** Each pharmacy is read from its own site — HTML price tables, WooCommerce variation endpoints, Shopify product JSON and JSON-LD — with article pages, blog posts and competitor comparison pages explicitly blocked, because those are the sources that produce plausible but wrong numbers. A price must not fall as the dose rises; violations are repaired by dropping the single implausible dose rather than discarding the pharmacy. The result is 68 listed pharmacies, 66 of them verified against the GPhC register.

**Compliance.** The product was rebuilt around UK medicines advertising rules rather than retrofitted. The home screen names no medicine and shows no price; the factual price list sits on a separate page, which the rules permit; and promotions were removed entirely, since offers on prescription medicine prices may not be highlighted. It also changed the default sort — from cheapest to easiest — so the app does not lead on price.

**Ease score.** A published-steps-only measure of how much a pharmacy asks of you: consultation, photo upload, repeat photo, video, ID, GP letter. Pharmacies that publish nothing score nothing, rather than scoring a perfect 100.

**Product and design.** A seven-option palette process with WCAG contrast measured for every colour pair — three of the supplied colours could not legally carry small text and were assigned tint-only roles. Four CSS interactions built in under 1KB instead of shipping an animation library, all gated behind `prefers-reduced-motion`.

**Delivery.** Capacitor shell around the web app, app icon and store screenshots at Apple's required 1179×2556, privacy manifest, export-compliance flag, and paste-ready App Store metadata.

---

## 3. LinkedIn / one-paragraph version

I built GLPenFind, an app that indexes what UK pharmacies charge for prescription weight-management pens. It reads prices from 68 pharmacies' own product pages, verifies every pharmacy against the GPhC register, and scores how much each one asks you to prove before you can order — then presents it under the UK rules that forbid promoting prescription medicines on price. The hard parts were not the scraping: they were deciding which numbers to trust, and rebuilding the entire interface once I understood that the regulations govern the home page, the ordering of results, and even the word "offer".

---

## Skills demonstrated

Data acquisition and cleaning (Playwright, structured-data parsing, source provenance) · Regulatory research and application (MHRA, GPhC) · Front-end engineering (vanilla JS, CSS design systems, accessibility) · iOS packaging (Capacitor, Xcode project, App Store Connect metadata) · Product definition under constraint

## Honest caveat

Do not claim App Store publication. The build is complete and staged; submission needs an Apple Developer account and Xcode, neither of which was in place. "Built and packaged for iOS" and "designed to App Store requirements" are both accurate.
