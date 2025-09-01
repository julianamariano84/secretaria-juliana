import sys
import os
import traceback

# ensure project root is on sys.path so `scheduler` package can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scheduler.terapee_scraper import TerapeeScraper

s = TerapeeScraper(headless=False)
print('configured=', s.configured)
try:
    print('starting login (verbose)')
    ok = s.login()
    print('login returned ->', ok)
    try:
        # attempt to capture page content and screenshot after login
        if getattr(s, '_page', None):
            html = s._page.content()
            with open('post_login_dump.html', 'w', encoding='utf-8') as f:
                f.write(html)
            s._page.screenshot(path='post_login.png', full_page=True)
            print('wrote post_login_dump.html and post_login.png')
        else:
            print('no page object available to dump')
    except Exception as e:
        print('failed to dump page after login:', e)
        traceback.print_exc()
    finally:
        s.close()
except Exception as e:
    print('login errored:', e)
    traceback.print_exc()
    try:
        s.close()
    except Exception:
        pass
print('done')
