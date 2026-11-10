#!/usr/bin/env python3
"""Hunt for price tables behind Treatment / Services menus.

Method (from watching a human do it):
  - home page -> menu links whose text looks like a treatment or services index
  - never follow "Get started", "Start consultation", "Assessment", "Register",
    "Sign in" — those lead into a questionnaire, not a price list
  - go two clicks deep, stop as soon as a page yields dose/price pairs
  - keep the HTML of whatever page worked, so the price can be re-checked

Writes reports/menu-probe.json and appends recoveries to the crawl journal.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/www/data")
ART = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/crawl-artifacts")
REPORT = Path("/Users/PetroulaKostofska/mounjaro-find-uk-ios/reports/menu-probe.json")
JRNL = Path("/Users/PetroulaKostofska/.hermes/cache/scratch/crawl_raw.jsonl")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")

FWD = re.compile(r"(2\.5|5|7\.5|10|12\.5|15)\s?mg[^\u00a3]{0,200}?\u00a3\s?(\d{2,3}(?:\.\d{2})?)", re.I)
REV = re.compile(r"\u00a3\s?(\d{2,3}(?:\.\d{2})?)[^\u00a3]{0,110}?(2\.5|5|7\.5|10|12\.5|15)\s?mg", re.I)

GOOD = [(r"treatment", 4), (r"weight\s*loss|weightloss", 4), (r"mounjaro", 5),
        (r"price|pricing|cost", 3), (r"service", 2), (r"medication|prescription", 2),
        (r"shop|buy", 1)]
BAD = re.compile(r"(get[- ]?started|start[- ]?(my|your)?[- ]?consultation|assessment|questionnaire|"
                 r"register|sign[- ]?up|sign[- ]?in|log[- ]?in|checkout|cart|basket|book|"
                 r"consultation$|consult\b|patient[- ]?portal|account)", re.I)


def score(text: str, href: str) -> int:
    blob = f"{text} {href}".lower()
    if BAD.search(blob):
        return -1
    s = 0
    for pat, weight in GOOD:
        if re.search(pat, blob):
            s += weight
    return s


def pairs(text: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for m in FWD.finditer(text):
        found.setdefault(m.group(1), float(m.group(2)))
    for m in REV.finditer(text):
        found.setdefault(m.group(2), float(m.group(1)))
    return {d: p for d, p in found.items() if 80 <= p <= 400}


def links(page, domain: str) -> list[tuple[int, str, str]]:
    raw = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => [e.href, (e.innerText||'').trim().slice(0,80)])")
    out = []
    seen = set()
    for href, text in raw:
        if not href or domain not in href:
            continue
        clean = href.split("#")[0].split("?")[0].rstrip("/")
        if clean in seen or clean.count("/") < 3:
            continue
        s = score(text, clean)
        if s < 2:
            continue
        seen.add(clean)
        out.append((s, clean, text))
    out.sort(key=lambda t: -t[0])
    return out[:8]


def accept_cookies(page) -> None:
    for label in ("Accept all", "Accept", "I agree", "Allow all"):
        try:
            btn = page.get_by_role("button", name=re.compile(f"^{label}$", re.I))
            if btn.count():
                btn.first.click(timeout=1500)
                page.wait_for_timeout(600)
                return
        except Exception:
            continue


def probe(page, name: str, domain: str) -> dict:
    out = {"provider": name, "domain": domain, "url": "", "prices": {}, "tried": []}
    try:
        page.goto(f"https://{domain}/", wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(1800)
        accept_cookies(page)

        first = links(page, domain)
        deepest: list[tuple[int, str, str]] = []
        for s, url, text in first[:4]:
            if len(out["prices"]) >= 4:
                break
            out["tried"].append(url)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2200)
                accept_cookies(page)
            except Exception:
                continue
            found = pairs(page.inner_text("body"))
            if len(found) > len(out["prices"]):
                out["prices"], out["url"] = found, url
            if len(found) >= 4:
                break
            deepest += [(s2, u2, t2) for s2, u2, t2 in links(page, domain)[:3]]

        for s, url, text in deepest[:6]:
            if len(out["prices"]) >= 4:
                break
            if url in out["tried"]:
                continue
            out["tried"].append(url)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(2200)
            except Exception:
                continue
            found = pairs(page.inner_text("body"))
            if len(found) > len(out["prices"]):
                out["prices"], out["url"] = found, url

        if out["url"]:
            ART.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            try:
                page.goto(out["url"], wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(1500)
                (ART / f"{slug}.html").write_text(page.content()[:2_000_000], encoding="utf-8")
            except Exception:
                pass
    except Exception as exc:
        out["error"] = str(exc)[:80]
    out["doses"] = len(out["prices"])
    return out


def main() -> None:
    index = json.loads((APP / "price-index.json").read_text())
    todo = [(u["provider"], u.get("domain", "")) for u in index["unread"] if u.get("domain")]
    print(f"probing {len(todo)} pharmacies", flush=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-GB", viewport={"width": 1440, "height": 950})
        page = ctx.new_page()
        for name, domain in todo:
            res = probe(page, name, domain)
            results.append(res)
            print(f"{name:<24} doses={res['doses']} {res.get('url','')[:64]}", flush=True)
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps(results, indent=1))
        ctx.close()
        browser.close()

    rec = [r for r in results if r["doses"] >= 3]
    print(f"\nrecovered {len(rec)}/{len(results)}: " + ", ".join(r["provider"] for r in rec))
    if rec:
        rows = {}
        if JRNL.exists():
            for line in JRNL.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    rows[row["provider"]] = row
        for r in rec:
            rows[r["provider"]] = {
                "provider": r["provider"], "domain": r["domain"], "prices": r["prices"],
                "page": r["url"], "status": f"200/{r['doses']}",
                "note": "found behind a treatment/services menu link",
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        JRNL.write_text("\n".join(json.dumps(v) for v in rows.values()) + "\n")
        print(f"journal now holds {len(rows)}")


if __name__ == "__main__":
    main()
