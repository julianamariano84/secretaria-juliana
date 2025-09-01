from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os

load_dotenv()
base = os.getenv("TERAPEE_BASE_URL", "https://app.terapee.com.br")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    url = base.rstrip('/') + "/painel"
    print("navigating to", url)
    page.goto(url, wait_until="load", timeout=10000)
    html = page.content()
    print("content length:", len(html))
    print(html[:2000])
    browser.close()
