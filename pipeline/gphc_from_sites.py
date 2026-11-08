#!/usr/bin/env python3
"""Find each pharmacy's GPhC registration number on its own website, then verify
it on the GPhC register.

Numbers inherited from third-party tables proved unreliable (column misalignment
in the source), so the only evidence we trust is the pharmacy publishing its own
registration number, confirmed against pharmacyregulation.org.

Output: www/data/gphc.json
"""
from __future__ import annotations

import difflib
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
REG = "https://www.pharmacyregulation.org"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()

# "GPhC 9012633", "GPhC registration number: 9012633", "registered with the GPhC (9012633)"
NUM_PATTERNS = [
    re.compile(r"gphc[^0-9]{0,45}?(\d{7})", re.I),
    re.compile(r"registration\s*(?:number|no\.?)[^0-9]{0,25}?(\d{7})", re.I),
    re.compile(r"pharmacyregulation\.org/registers/pharmacy/(?:registrationnumber/)?(\d{7})", re.I),
]
PATHS = ["", "/contact", "/contact-us", "/terms", "/terms-and-conditions", "/about", "/about-us", "/legal"]


def get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-GB,en"})
    try:
        with urllib.request.urlopen(req, timeout=18, context=CTX) as r:
            return r.status, r.read(1_500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def numbers_on(domain: str) -> tuple[list[str], str]:
    """Numbers published by the pharmacy itself, plus the page they came from."""
    found: list[str] = []
    where = ""
    for path in PATHS:
        status, body = get(f"https://{domain}{path}")
        if status != 200:
            continue
        text = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        for pat in NUM_PATTERNS:
            for m in pat.finditer(text):
                num = m.group(1)
                if num not in found:
                    found.append(num)
                    if not where:
                        where = f"https://{domain}{path}"
        if len(found) >= 3:
            break
    return found, where


def register_row(number: str) -> dict | None:
    status, body = get(f"{REG}/registers/pharmacy/registrationnumber/{number}")
    if status != 200:
        return None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        cells = [c for c in cells if c]
        if len(cells) >= 5 and cells[3].replace(" ", "") == number:
            return {"registered_name": re.sub(r"\s*See registration details$", "", cells[0]),
                    "owner": cells[1], "address": cells[2], "status": cells[4]}
    return None


def resolve(provider: str, domain: str) -> dict:
    out = {"provider": provider, "domain": domain, "verified": False, "number": None}
    if not domain:
        out["error"] = "no domain"
        return out
    nums, where = numbers_on(domain)
    out["evidence_url"] = where
    out["candidates"] = nums
    best = None
    for num in nums:
        row = register_row(num)
        if not row:
            continue
        score = difflib.SequenceMatcher(None, provider.lower(), row["registered_name"].lower()).ratio()
        # a number published by the pharmacy itself is evidence even when the
        # registered entity name differs (trading name vs registered name)
        candidate = {**row, "number": num, "match": round(score, 2)}
        if best is None or candidate["match"] > best["match"]:
            best = candidate
    if best:
        out.update(best)
        out["verified"] = best["status"].lower().startswith("registered")
        out["method"] = "site-published number, confirmed on register"
    else:
        out["error"] = "no registration number found on site" if not nums else "number not on register"
    return out


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    rows = [(p["provider"], p.get("domain", "")) for p in index["providers"]]
    rows += [(u["provider"], u.get("domain", "")) for u in index.get("unread", [])]
    rows = [(n, d) for n, d in rows if d]

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(resolve, n, d): n for n, d in rows}
        for i, f in enumerate(futs, 1):
            pass
        for fut, name in futs.items():
            try:
                res = fut.result()
            except Exception as exc:
                res = {"provider": name, "verified": False, "error": str(exc)[:60]}
            results[res["provider"]] = res

    payload = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": "number published on the pharmacy's own site, confirmed against pharmacyregulation.org",
               "providers": results}
    (APP / "gphc.json").write_text(json.dumps(payload, indent=1))

    ok = {n: r for n, r in results.items() if r.get("verified")}
    print(f"verified {len(ok)}/{len(results)}")
    for n, r in sorted(ok.items()):
        print(f"  {n:<26} {r['number']}  {r.get('registered_name','')[:32]:<32} {r['status']}")
    misses = [n for n, r in results.items() if not r.get("verified")]
    print(f"\nno number found on site ({len(misses)}): {', '.join(sorted(misses))}")


if __name__ == "__main__":
    main()
