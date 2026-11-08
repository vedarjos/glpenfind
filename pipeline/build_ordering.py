#!/usr/bin/env python3
"""Build data/ordering.json: what each pharmacy actually asks of you.

Evidence comes from two places, both first-party:
  1. rendered HTML of the pharmacy's own Mounjaro page (crawl-artifacts/)
  2. the hand-researched provider notes in this repo (research/2026-04-03-uk-market-snapshot.md)

Each detected step keeps the matched phrase so the app can show its working.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCRATCH = Path("/Users/PetroulaKostofska/.hermes/cache/scratch")
OUT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
ART = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/crawl-artifacts")

PATTERNS = {
    "questionnaire": r"(online consultation|questionnaire|clinical assessment|short assessment|answer a few questions)",
    "photo": r"(upload a photo|photo of yourself|photograph yourself|take a photo|full[- ]body photo|body shot)",
    "repeat_photo": r"((every|after) (three|four|\d+) (months|weeks)[^.]{0,60}photo|repeat photo|monitoring photo|photos? (again|every))",
    "video": r"(video consult|video call|video verification|video proof|liveness check)",
    "id": r"(passport|driving licen[cs]e|proof of identity|photo id\b)",
    "gp": r"((gp|doctor)'?s? (records|details|letter|summary)|summary care record|contact your gp|gp verification|clinical records( check)?)",
    "slow": r"((three|four|five|seven|\d+) (working )?days (to|for) (review|approv|dispatch))",
}
APPROVAL = re.compile(r"within (\d+|twenty[- ]four|forty[- ]eight) (hours|days)", re.I)
DELIVERY = re.compile(r"(royal mail tracked \d+|next[- ]day delivery|free delivery|delivery (is )?included|"
                      r"tracked \d+ ?(hour|hr))", re.I)
# only real new-customer offers: stated as first order, or an ALLCAPS code token
CODE = re.compile(r"((?:£\d+|\d+%)\s?off (?:your |the )?(?:first|1st) (?:order|purchase)|"
                  r"(?:£\d+|\d+%)\s?off for new customers|"
                  r"up to \d+% off (?:your )?first order)")

# Hand-researched from provider pages (see research/2026-04-03-uk-market-snapshot.md).
RESEARCHED = {
    "Superdrug Online Doctor": dict(steps=["questionnaire", "photo", "repeat_photo", "slow"],
                                    approval_days=1,
                                    evidence="photos before start, again after 3-4 months and annually; 24h approval target"),
    "Numan": dict(steps=["questionnaire", "photo", "id"], approval_days=None,
                  evidence="ID, body shots and current medication evidence required"),
    "MedExpress": dict(steps=["questionnaire", "id", "gp"], approval_days=None,
                       evidence="GPhC inspection action plan points to stronger verification and review controls"),
    "Boots Online Doctor": dict(steps=["questionnaire"], approval_days=1,
                                evidence="online consultation, clinician review within 24h"),
    "Medicine Marketplace": dict(steps=["questionnaire", "id"], approval_days=1,
                                 evidence="new customers may need ID and weight information; repeat orders lighter"),
    "Oxford Online Pharmacy": dict(steps=["questionnaire"], approval_days=None,
                                   evidence="consultation required; no explicit photo or video requirement found"),
    "Cloud Pharmacy": dict(steps=["questionnaire"], approval_days=None,
                           evidence="short assessment required before treatment recommendation"),
}

def _norm(name: str) -> str:
    n = re.sub(r"[^a-z0-9]+", " ", name.lower())
    for junk in ("online doctor", "online pharmacy", "pharmacy", "online", "weight loss clinic"):
        n = n.replace(junk, " ")
    return re.sub(r"\s+", " ", n).strip()


def researched_for(name: str):
    direct = RESEARCHED.get(name)
    if direct:
        return direct
    target = _norm(name)
    for key, val in RESEARCHED.items():
        k = _norm(key)
        if k and (target.startswith(k) or k.startswith(target)):
            return val
    return None


def _norm_delivery(raw: str) -> str:
    d = re.sub(r"\s+", " ", raw.strip().lower())
    d = d.replace("next-day", "next day").replace("next day", "next-day")
    return d[:1].upper() + d[1:]


def scan(text: str) -> dict:
    steps, evidence = [], []
    for key, pat in PATTERNS.items():
        m = re.search(pat, text, re.I)
        if m:
            steps.append(key)
            start = max(0, m.start() - 60)
            evidence.append(f"{key}: …{re.sub(r'\s+', ' ', text[start:m.end() + 60]).strip()[:150]}…")
    approval = None
    am = APPROVAL.search(text)
    if am:
        raw = am.group(1).lower()
        approval = 1 if raw in ("twenty-four", "24") else 2 if raw in ("forty-eight", "48") else int(re.sub(r"\D", "", raw) or 0) or None
    dm = DELIVERY.search(text)
    cm = CODE.search(text)
    return {
        "steps": steps,
        "approval_days": approval,
        "delivery": _norm_delivery(dm.group(1)) if dm else None,
        "code": re.sub(r"\s+", " ", cm.group(1)).strip().rstrip(",") if cm else None,
        "evidence": evidence,
    }


def main() -> None:
    raw = [json.loads(l) for l in (SCRATCH / "crawl_raw.jsonl").read_text().splitlines() if l.strip()]
    ratings = {p["provider"]: p for p in json.loads((SCRATCH / "provider_list.json").read_text())}

    providers: dict[str, dict] = {}
    for r in raw:
        name = r["provider"]
        entry = {
            "steps": [], "approval_days": None, "delivery": None, "code": None,
            "domain": r.get("domain") or "", "rating": None, "reviews": None,
            "rating_source": None, "evidence": [], "source": r.get("page") or "",
        }
        art = ART / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".html")
        if art.exists():
            found = scan(art.read_text(encoding="utf-8", errors="replace"))
            entry.update({k: found[k] for k in ("steps", "approval_days", "delivery", "code", "evidence")})

        research = researched_for(name)
        if research and not entry["steps"]:
            entry.update(research)
            entry["evidence"] = [f"researched: {research['evidence']}"]
        elif research:
            entry["evidence"].append(f"researched: {research['evidence']}")
            entry["steps"] += [s2 for s2 in research["steps"] if s2 not in entry["steps"]]
            if not entry.get("approval_days"):
                entry["approval_days"] = research.get("approval_days")

        providers[name] = entry

    # what we saw ourselves wins over what a page happens to admit
    manual_path = Path(__file__).with_name("manual_steps.json")
    if manual_path.exists():
        manual = json.loads(manual_path.read_text())
        for name, ov in manual.items():
            if name.startswith("_") or not isinstance(ov, dict):
                continue
            entry = providers.get(name)
            if not entry:
                continue
            entry["steps"] = sorted(set(entry.get("steps", [])) | set(ov.get("steps", [])))
            for key in ("approval_days", "delivery"):
                if ov.get(key):
                    entry[key] = ov[key]
            if "code" in ov:
                entry["code"] = ov["code"]
            if ov.get("note"):
                entry.setdefault("evidence", []).append(f"seen by hand: {ov['note']}")
            if ov.get("source"):
                entry["hand_checked_source"] = ov["source"]
            if ov.get("advertised_rating"):
                entry["advertised_rating"] = ov["advertised_rating"]
            entry["hand_checked"] = ov.get("checked_at")

    # attach Trustpilot scores fetched from trustpilot.com itself
    ratings_path = OUT / "ratings.json"
    if ratings_path.exists():
        by_domain = json.loads(ratings_path.read_text()).get("by_domain", {})
        for entry in providers.values():
            hit = by_domain.get(entry.get("domain", ""))
            if hit and hit.get("rating"):
                entry["rating"] = hit["rating"]
                entry["reviews"] = hit.get("reviews")
                entry["rating_source"] = "uk.trustpilot.com"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "weights": {"questionnaire": 10, "photo": 15, "repeat_photo": 15, "video": 20, "id": 10, "gp": 10, "slow": 5},
        "providers": providers,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ordering.json").write_text(json.dumps(payload, indent=1))
    with_steps = sum(1 for v in providers.values() if v["steps"])
    print(f"wrote {OUT/'ordering.json'} — {len(providers)} providers, {with_steps} with detected steps")
    for n, v in list(providers.items())[:12]:
        print(f"  {n[:26]:<26} {','.join(v['steps']) or '-'}  approval={v['approval_days']}  deliv={v['delivery']}")


if __name__ == "__main__":
    main()
