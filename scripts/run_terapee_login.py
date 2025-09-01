from dotenv import load_dotenv
import os, sys, traceback

# Ensure repo root is on sys.path so sibling packages (like `scheduler`) can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv()

from scheduler.terapee_scraper import TerapeeScraper

def main():
    headless_env = os.getenv("HEADLESS", "True")
    headless = not (headless_env.lower() in ("false", "0", "no"))

    s = TerapeeScraper(headless=headless)
    try:
        print("Starting Terapee UI login...")
        ok = s.login()
        if ok:
            print("LOGIN_OK")
            return 0
        else:
            print("LOGIN_FAILED")
            return 2
    except Exception as e:
        print("LOGIN_ERROR")
        traceback.print_exc()
        return 1
    finally:
        try:
            s.close()
        except Exception:
            pass

if __name__ == '__main__':
    sys.exit(main())
