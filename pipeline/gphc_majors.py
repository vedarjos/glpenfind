#!/usr/bin/env python3
"""Targeted verification for the high-street brands, using candidate numbers
found in search results, matched against the register by name or owner."""
import html, json, re, time
from pathlib import Path
from playwright.sync_api import sync_playwright

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
REG = "https://www.pharmacyregulation.org"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CANDIDATES = {
 "Boots": ["1096181"],
 "SuperDrug": ["1028947", "1084610", "9010736"],
 "Asda": ["1028656", "1091675", "9012976", "9013013"],
 "Lloyds Pharmacy": ["9011008", "9011437"],
 "Medicine Marketplace": ["1116946"],
 "Oxford Online Pharmacy": ["9012796"],
 "Cloud Pharmacy": ["9012073", "9012911"],
 "Numan": ["9011408"],
}
KEYWORDS = {"Boots": ["boots"], "SuperDrug": ["superdrug"], "Asda": ["asda"],
            "Lloyds Pharmacy": ["lloyds"], "Medicine Marketplace": ["medicine marketplace"],
            "Oxford Online Pharmacy": ["oxford"], "Cloud Pharmacy": ["cloud"], "Numan": ["numan"]}

def parse(body, num):
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        cells = [c for c in cells if c]
        if len(cells) >= 5 and cells[3].replace(" ", "") == num:
            return {"registered_name": re.sub(r"\s*See registration details$", "", cells[0]),
                    "owner": cells[1], "address": cells[2], "status": cells[4]}
    return None

data = json.loads((APP / "gphc.json").read_text())
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, locale="en-GB")
    page = ctx.new_page()
    for name, nums in CANDIDATES.items():
        cur = data["providers"].get(name, {"provider": name, "verified": False})
        if cur.get("verified"):
            continue
        for num in nums:
            try:
                page.goto(f"{REG}/registers/pharmacy/registrationnumber/{num}", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
                row = parse(page.content(), num)
            except Exception as exc:
                row = None
            if row:
                blob = (row["registered_name"] + " " + row["owner"]).lower()
                hit = any(k in blob for k in KEYWORDS[name])
                print(f"  {name:<24} {num} -> {row['registered_name'][:34]:<34} owner={row['owner'][:26]:<26} match={hit}")
                if hit:
                    cur.update(row)
                    cur.update({"number": num, "verified": row["status"].lower().startswith("registered"),
                                "method": "register match on brand owner name"})
                    cur.pop("candidate_rejected", None)
                    data["providers"][name] = cur
                    break
            else:
                print(f"  {name:<24} {num} -> no row")
            time.sleep(7)
        APP.joinpath("gphc.json").write_text(json.dumps(data, indent=1))
    ctx.close(); b.close()
ok = sum(1 for r in data["providers"].values() if r.get("verified"))
print(f"verified now {ok}/{len(data['providers'])}")
