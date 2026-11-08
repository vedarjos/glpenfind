#!/usr/bin/env python3
"""Check the handful of answers that the first pass could not settle."""
import html, re, ssl, urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()

CHECKS = {
 "Numan": ["https://www.numan.com/weight-loss/mounjaro", "https://www.numan.com/weight-loss"],
 "Trim": ["https://gettrim.co.uk/pages/faq", "https://gettrim.co.uk/pages/mounjaro-for-postpartum-weight-loss"],
 "Curate": ["https://curatehealth.co.uk/weight-loss/mounjaro", "https://curatehealth.co.uk/help"],
 "Cured Pharmacy": ["https://curedpharmacy.com/pages/cheapest-mounjaro-uk", "https://curedpharmacy.com/pages/faq"],
 "MedExpress": ["https://www.medexpress.co.uk/clinics/weight-loss/mounjaro"],
 "UK Meds": ["https://www.ukmeds.co.uk/mounjaro"],
 "EverydayMeds": ["https://everydaymeds.co.uk/products/mounjaro-injection", "https://everydaymeds.co.uk/pages/faq"],
 "Oxford Online Pharmacy": ["https://www.oxfordonlinepharmacy.co.uk/weight-loss/mounjaro"],
 "The Care Pharmacy": ["https://thecarepharmacy.com/mounjaro-price-comparison-uk"],
 "Pharmica": ["https://www.pharmica.co.uk/weight-loss/mounjaro"],
 "Ashcroft Pharmacy": ["https://www.ashcroftpharmacy.co.uk/online-doctor/weight-loss/weight-loss-mounjaro"],
 "Pharmacy Planet": ["https://www.pharmacyplanet.com/mounjaro.html"],
}
PATTERNS = {
 "bmi": r"[^.|]{0,110}BMI[^.|]{0,140}",
 "photo": r"[^.|]{0,110}(?:photo|photograph|picture)[^.|]{0,140}",
 "email_gp": r"[^.|]{0,90}(?:GP|medical records|summary care record)[^.|]{0,110}",
}

def text_of(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            b = r.read(1_500_000).decode("utf-8", "replace")
    except Exception as e:
        return f"__ERR__{e}"
    b = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", b)))

for name, urls in CHECKS.items():
    print(f"\n### {name}")
    for url in urls:
        t = text_of(url)
        if t.startswith("__ERR__"):
            print(f"  ! {url[:60]} {t[:50]}")
            continue
        for field, pat in PATTERNS.items():
            hits = []
            for m in re.finditer(pat, t, re.I):
                s = m.group(0).strip()
                if len(s) > 30 and not any(s[:40] in h for h in hits):
                    hits.append(s)
            for h in hits[:2]:
                print(f"  {field}: {h[:180]}")
