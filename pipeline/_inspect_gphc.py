from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
with sync_playwright() as pw:
    b=pw.chromium.launch(); c=b.new_context(user_agent=UA); p=c.new_page()
    for url in ["https://www.pharmacyregulation.org/registers/pharmacy/registrationnumber"]:
        p.goto(url, wait_until="domcontentloaded", timeout=30000); p.wait_for_timeout(2000)
        print("final:", p.url)
        print("inputs:", p.eval_on_selector_all("input", "els=>els.map(e=>e.name+':'+e.type)"))
        print("forms:", p.eval_on_selector_all("form", "els=>els.map(e=>e.action+' '+e.method)"))
    b.close()
