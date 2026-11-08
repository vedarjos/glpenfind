#!/usr/bin/env python3
"""Turn raw crawl output into the app's price index, with hygiene checks.

Rules:
  * a provider's price must never fall as the dose rises (catches pages where a
    "from" price or a discount was scraped into the wrong dose row)
  * >=4 doses on one page = high confidence; 1-3 doses = medium
  * anything failing the monotonic check is held back in review.json, not shown
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SCRATCH = Path("/Users/PetroulaKostofska/.hermes/cache/scratch")
OUT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
DOSES = ["2.5", "5", "7.5", "10", "12.5", "15"]


def monotonic(prices: dict[str, float]) -> bool:
    seq = [prices[d] for d in DOSES if d in prices]
    return all(b >= a - 0.01 for a, b in zip(seq, seq[1:]))


def repair(prices: dict[str, float]) -> dict[str, float]:
    """Drop doses until the remaining set is monotonic, keeping the most doses.

    A single mis-read figure (consultation fee, multi-month pack, bundle total)
    should not cost us the whole pharmacy.
    """
    kept = dict(prices)
    while len(kept) >= 2 and not monotonic(kept):
        seq = [(d, kept[d]) for d in DOSES if d in kept]
        worst_dose, worst_gap = None, 0.0
        for (d1, p1), (d2, p2) in zip(seq, seq[1:]):
            if p2 < p1 and (p1 - p2) > worst_gap:
                worst_dose, worst_gap = d2, p1 - p2
        if worst_dose is None:
            break
        kept.pop(worst_dose)
    return kept


def main() -> None:
    dedup = {}
    for line in (SCRATCH / "crawl_raw.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            dedup[r["provider"]] = r

    good, review, repaired_rows = [], [], []
    for r in dedup.values():
        prices = {d: v for d, v in r["prices"].items() if d in DOSES}
        if not prices:
            continue
        rec = {
            "provider": r["provider"],
            "gphc": r.get("gphc") or "",
            "domain": r.get("domain") or "",
            "prices_gbp": dict(sorted(prices.items(), key=lambda kv: float(kv[0]))),
            "source_url": r.get("page") or "",
            "retrieved_at": r.get("retrieved_at") or "",
            "doses_found": len(prices),
            "confidence": "high" if len(prices) >= 4 else "medium",
        }
        if not monotonic(prices):
            # salvage what is sound: drop the dose with the worst violation and
            # try again, rather than throwing away a whole pharmacy over one
            # mis-read figure (a consultation fee, a multi-month pack, a bundle)
            repaired = repair(prices)
            if len(repaired) >= 2:
                dropped = sorted(set(prices) - set(repaired), key=float)
                rec["prices_gbp"] = dict(sorted(repaired.items(), key=lambda kv: float(kv[0])))
                rec["doses_found"] = len(repaired)
                rec["confidence"] = "medium" if len(repaired) < 4 else "high"
                rec["note"] = "dropped implausible dose(s): " + ", ".join(f"{d}mg" for d in dropped)
                rec["reason"] = "price fell as dose rose — one or more doses discarded"
                good.append(rec)
                repaired_rows.append(rec)
                continue
            rec["reason"] = "price fell as dose rose — needs manual check"
            review.append(rec)
        else:
            good.append(rec)

    good.sort(key=lambda p: p["prices_gbp"].get("7.5", 999))

    # providers we know exist and price-check, but which hid prices behind a
    # consultation or a bot wall on this pass — shown, honestly, as unread
    known_unread = []
    for name, r in dedup.items():
        if not r["prices"] and r.get("domain"):
            known_unread.append({"provider": name, "domain": r["domain"],
                                 "source_url": r.get("page") or f"https://{r['domain']}/",
                                 "price_found": False})

    # attach a reason to each unread row so the app can say *why* it has no price
    why_path = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/reports/why-unread.json")
    if why_path.exists():
        why = {r["provider"]: r for r in json.loads(why_path.read_text())}
        for u in known_unread:
            r = why.get(u["provider"])
            if not r:
                continue
            if r.get("gate"):
                u["reason"] = "price shown only after their consultation"
            elif (r.get("home_status") or 0) != 200:
                u["reason"] = f"site did not load for us (HTTP {r.get('home_status')})"
            else:
                u["reason"] = "no price on the pages we could reach"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": ("Prices read directly from each pharmacy's own Mounjaro page by a "
                   "headless-Chromium crawler. Every row keeps the exact page and the "
                   "time it was read. No aggregator database is copied."),
        "attribution": ("Discount codes and delivery terms shown only where the pharmacy "
                        "states them on the page we read. Checkout is the final word."),
        "doses": DOSES,
        "providers": good,
        "unread": known_unread,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "price-index.json").write_text(json.dumps(payload, indent=1))
    (SCRATCH / "review.json").write_text(json.dumps(review, indent=1))

    six = [p for p in good if p["doses_found"] >= 4]
    print(f"indexed {len(good)} providers ({len(six)} with 4+ doses), "
          f"{len(known_unread)} known-unread, {len(review)} held for review, "
          f"{len(repaired_rows)} repaired")
    for p in sorted(good, key=lambda p: p["prices_gbp"].get("2.5", 999))[:12]:
        pr = p["prices_gbp"]
        print(f"  {p['provider'][:26]:<26} 2.5={pr.get('2.5','—'):>7} 7.5={pr.get('7.5','—'):>7} 15={pr.get('15','—'):>7}")


if __name__ == "__main__":
    main()
