#!/usr/bin/env python3
"""Verify second-pass candidates against the register and merge into gphc.json."""
import html, json, re, ssl, urllib.request
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
REG = "https://www.pharmacyregulation.org"
CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Macintosh) Chrome/131"

def row_for(num: str):
    req = urllib.request.Request(f"{REG}/registers/pharmacy/registrationnumber/{num}",
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as r:
            body = r.read(1_500_000).decode("utf-8", "replace")
    except Exception:
        return None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        cells = [c for c in cells if c]
        if len(cells) >= 5 and cells[3].replace(" ", "") == num:
            return {"registered_name": re.sub(r"\s*See registration details$", "", cells[0]),
                    "owner": cells[1], "address": cells[2], "status": cells[4]}
    return None

data = json.loads((APP / "gphc.json").read_text())
cands = json.loads((APP / "gphc_candidates.json").read_text())
added = 0
for name, (num, where) in cands.items():
    cur = data["providers"].get(name, {"provider": name, "verified": False})
    if cur.get("verified"):
        continue
    row = row_for(num)
    if not row:
        cur["candidate_rejected"] = {"number": num, "reason": "not a pharmacy on the register", "where": where}
        data["providers"][name] = cur
        continue
    cur.update(row)
    cur.update({"number": num, "verified": row["status"].lower().startswith("registered"),
                "method": "number found on own site (second pass), confirmed on register",
                "evidence_url": where})
    data["providers"][name] = cur
    added += row["status"].lower().startswith("registered")
    print(f"  + {name:<26} {num} {row['registered_name'][:30]:<30} {row['status']}")
(APP / "gphc.json").write_text(json.dumps(data, indent=1))
ok = sum(1 for r in data["providers"].values() if r.get("verified"))
print(f"\nmerged {added} new; total verified {ok}/{len(data['providers'])}")
