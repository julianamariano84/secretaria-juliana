from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()
# Default profile path (assumption). Change PROFILE_DIR env var to override.
default_profile = r"C:\Users\mario\AppData\Local\Google\Chrome\User Data\Default"
profile_dir = os.getenv("PROFILE_DIR", default_profile)
base = os.getenv("TERAPEE_BASE_URL", "https://app.terapee.com.br")

print("Using profile:", profile_dir)

with sync_playwright() as p:
    # use persistent context so it uses saved passwords/ autofill
    ctx = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=False)
    page = ctx.new_page()
    url = base.rstrip('/') + "/painel"
    print("navigating to", url)
    page.goto(url, wait_until="networkidle", timeout=60000)
    # give time for autofill/extensions to act
    time.sleep(5)
    html = page.content()
    print("content length:", len(html))
    with open("dump_with_profile.txt", "w", encoding="utf-8") as f:
        f.write(html)
    page.screenshot(path="dump_with_profile.png", full_page=True)
    print("wrote dump_with_profile.txt and dump_with_profile.png")
    # keep browser open briefly so user can inspect
    time.sleep(3)
    ctx.close()
