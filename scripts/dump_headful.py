from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()
base = os.getenv("TERAPEE_BASE_URL", "https://app.terapee.com.br")

with sync_playwright() as p:
    # headful so the user can see autofill
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context()
    page = ctx.new_page()
    url = base.rstrip('/') + "/painel"
    print("navigating to", url)
    page.goto(url, wait_until="networkidle", timeout=30000)
    # give time for browser autofill/extensions to act
    time.sleep(5)
    html = page.content()
    print("content length:", len(html))
    with open("dump_out_headful.txt", "w", encoding="utf-8") as f:
        f.write(html)
    page.screenshot(path="dump_out_headful.png", full_page=True)
    print("wrote dump_out_headful.txt and dump_out_headful.png")
    # keep browser open briefly so user can inspect
    time.sleep(3)
    browser.close()
