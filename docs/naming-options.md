# App name options

Checked 31 Oct 2026: `.com` and `.co.uk` via RDAP (404 = unregistered), App Store GB via the
iTunes Search API. Re-check before buying — domain status changes daily.

## The trade-off nobody escapes

A name that sounds like "Mounjaro" is, by definition, the name most likely to be challenged.
Trademark law tests similarity *and* the likelihood of confusion — and an app listing the same
drug's prices in the same category is precisely the setting where confusion is presumed. Apple
adds rule 5.2.1 (no implying affiliation). So the safer play is a name that evokes the *category*
rather than the *brand*: same rhythm, different letters, its own meaning.

## Shortlist, tested

| Name | Sounds like | .com | .co.uk | App Store GB hits |
|---|---|---|---|---|
| **Menjira** | men-JEE-ra — same cadence, distinct consonants | free | free | **0** |
| **Monjira** | mon-JEE-ra — keeps the "Monj" shape | free | free | 1 (unrelated instrument app) |
| Monjari | mon-JAR-ee — closest to the original | free | free | 10 |
| Monjarra | mon-JAR-ra | free | free | 8 |
| Manjarro | man-JAR-ro | free | free | 9 |
| Jab Index | jab-in-dex — descriptive | free | free | 4 |

Already taken and therefore out: Manjaro, Marajo, Munro, Jarrow, Jarrah, Majaro, Javaro,
Jandaro, Mandaro, DoseIndex.

## Recommendation

- **Safest, and genuinely free: Menjira.** Zero App Store collisions in GB, both domains open,
  and one letter of distance from the word that would cause trouble.
- **If the sound-alike matters more than the margin of safety: Monjira.** Warmer, closer to the
  product people know, still available — but a challenge is more plausible, and "Monj-" is the
  distinctive part of the trademark.
- Do not use either *with* "Mounjaro" in the title. Keeping the drug name to the subtitle and
  description is the difference between descriptive use and an implied endorsement.

## On "Mounjaro-find-UK"

Good repo, handle and domain name — bad App Store title. Three reasons: hyphens read as a URL
rather than a brand, "find" is filler that carries no promise, and it puts the trademark in the
one field Apple scrutinises hardest. Keep it as the GitHub name and the thing you type in a
browser; put a coined name on the store listing.

## Next steps if a name is chosen

1. Register `.com` and `.co.uk` the same day — at least one of the pair will be gone soon after.
2. Check UKIPO for conflicts in class 9 (software) and class 44 (medical information).
3. Update `appName` in `capacitor.config.ts`, `CFBundleDisplayName`, the icon, and the store listing.
