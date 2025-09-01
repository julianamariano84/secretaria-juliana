from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time
import traceback

load_dotenv()
default_profile = r"C:\Users\mario\AppData\Local\Google\Chrome\User Data\Default"
profile_dir = os.getenv("PROFILE_DIR", default_profile)
base = os.getenv("TERAPEE_BASE_URL", "https://app.terapee.com.br")

out_html = "dump_with_profile_verbose.txt"
out_png = "dump_with_profile_verbose.png"
log_file = "dump_with_profile_verbose.log"

with open(log_file, "w", encoding="utf-8") as log:
    try:
        log.write(f"Using profile: {profile_dir}\n")
        log.flush()
        with sync_playwright() as p:
            log.write("starting playwright\n")
            log.flush()
            # use persistent context so it uses saved passwords/ autofill
            ctx = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=False)
            page = ctx.new_page()
            url = base.rstrip('/') + "/painel"
            log.write(f"navigating to {url}\n")
            log.flush()
            page.goto(url, wait_until="networkidle", timeout=60000)
            # give time for autofill/extensions to act
            time.sleep(5)
            try:
                html = page.content()
                with open(out_html, "w", encoding="utf-8") as f:
                    f.write(html)
                page.screenshot(path=out_png, full_page=True)
                log.write(f"wrote {out_html} ({len(html)} bytes) and {out_png}\n")
            except Exception as e_inner:
                log.write(f"failed capturing content/screenshot: {e_inner}\n")
                log.write(traceback.format_exc())
            # keep browser open briefly so user can inspect (3s)
            time.sleep(3)
            ctx.close()
            log.write("closed context\n")
    except Exception as e:
        log.write(f"exception during run: {e}\n")
        log.write(traceback.format_exc())

print("script finished; check dump files and log")
