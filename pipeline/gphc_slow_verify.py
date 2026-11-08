#!/usr/bin/env python3
"""Verify remaining candidates one at a time in a real browser, slowly.

The register blocks rapid programmatic requests (403), so this pass throttles to
one lookup every few seconds and parses the rendered table.
"""
import html, json, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
REG = "https://www.pharmacyregulation.org"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")

def parse(body: str, num: str):
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
todo = {n: v for n, v in cands.items() if not data["providers"].get(n, {}).get("verified")}
print("to verify:", len(todo))

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, locale="en-GB")
    page = ctx.new_page()
    for name, (num, where) in todo.items():
        cur = data["providers"].get(name, {"provider": name, "verified": False})
        try:
            page.goto(f"{REG}/registers/pharmacy/registrationnumber/{num}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1200)
            row = parse(page.content(), num)
        except Exception as exc:
            row = None
            cur["last_error"] = str(exc)[:60]
        if row:
            cur.update(row)
            cur.update({"number": num, "verified": row["status"].lower().startswith("registered"),
                        "method": "number found on own site, confirmed on register",
                        "evidence_url": where})
            cur.pop("candidate_rejected", None)
            print(f"  OK {name:<26} {num} {row['registered_name'][:30]:<30} {row['status']}")
        else:
            print(f"  -- {name:<26} {num} no register row")
        data["providers"][name] = cur
        APP.joinpath("gphc.json").write_text(json.dumps(data, indent=1))
        time.sleep(4)
    ctx.close(); b.close()

ok = sum(1 for r in data["providers"].values() if r.get("verified"))
print(f"\nverified now {ok}/{len(data['providers'])}")
