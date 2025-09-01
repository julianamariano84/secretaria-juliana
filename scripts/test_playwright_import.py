from dotenv import load_dotenv
import os, traceback

load_dotenv()

print("ENV TERAPEE_BASE_URL=", os.getenv("TERAPEE_BASE_URL"))
print("ENV TERAPEE_UI_USER=", os.getenv("TERAPEE_UI_USER"))
print("ENV HEADLESS=", os.getenv("HEADLESS"))

try:
    from playwright.sync_api import sync_playwright
    print("PLAYWRIGHT_AVAILABLE=True")
    # quick check: start and stop without launching a browser to ensure install
    p = sync_playwright().start()
    p.stop()
    print("PLAYWRIGHT_STARTSTOP=OK")
except Exception as e:
    print("PLAYWRIGHT_AVAILABLE=False", str(e))
    traceback.print_exc()
