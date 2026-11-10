#!/usr/bin/env python3
"""Decide which register entries belong to the pharmacy that published the number.

A pharmacy may trade under a different registered name ("WePrescribe" is
registered as "We Prescribe"), so compare on a collapsed alphanumeric form and
accept equal, prefix, high-similarity, or shared distinctive token. Anything
else is kept but marked unconfirmed and never shown as a badge.
"""
import difflib, json, re
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
GENERIC = {"pharmacy","online","doctor","health","clinic","weight","loss","uk","ltd","limited",
           "the","care","meds","medical","direct","group","services","chemist","prescription",
           "and","of","co","company","healthcare","wellness","shop","store","hq","operations"}

def collapse(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def toks(s: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9]+", (s or "").lower()) if p not in GENERIC and len(p) >= 4}

def confident(provider: str, reg_name: str, owner: str) -> bool:
    a, b = collapse(provider), collapse(reg_name)
    if not b:
        return False
    if a == b:
        return True
    if (a.startswith(b) or b.startswith(a)) and min(len(a), len(b)) >= 5:
        return True
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio >= 0.72:
        return True
    # shared stem, e.g. "genmeds" vs "genmedical"
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    if common >= 5 and ratio >= 0.6:
        return True
    pt, rt = toks(provider), toks(reg_name) | toks(owner)
    if pt & rt:
        return True
    return False

data = json.loads((APP / "gphc.json").read_text())
kept, dropped = [], []
for name, r in data["providers"].items():
    if not r.get("number"):
        if r.get("unconfirmed"):
            r["verified"] = False
        continue
    ok = r.get("status","").lower().startswith("registered") and confident(
        name, r.get("registered_name",""), r.get("owner",""))
    r["verified"] = ok
    if ok:
        kept.append(name)
        r.pop("unconfirmed", None)
    else:
        dropped.append((name, r.get("registered_name"), r.get("owner")))
        r["unconfirmed"] = {"number": r.get("number"), "registered_name": r.get("registered_name"),
                            "owner": r.get("owner"),
                            "reason": "register entry could not be tied to this pharmacy"}

(APP / "gphc.json").write_text(json.dumps(data, indent=1))
print(f"confident: {len(kept)}   unconfirmed: {len(dropped)}")
for n, rn, ow in dropped:
    print(f"  ? {n:<24} -> {rn} ({ow})")
