from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os, time, sys, traceback

load_dotenv()
profile_dir = os.getenv('PROFILE_DIR', r"C:\Users\mario\AppData\Local\Google\Chrome\User Data\Default")
base = os.getenv('TERAPEE_BASE_URL', 'https://app.terapee.com.br')

selectors_username = [
    "input[name='email']",
    "input[type='email']",
    "input[name='username']",
    "input[placeholder*='E-mail']",
    "input[placeholder*='Email']",
    "input[aria-label*='E-mail']",
    "input[aria-label*='Email']",
    "input[type='text']",
    "input"
]
selectors_password = [
    "input[type='password']",
    "input[name='password']",
    "input[placeholder*='Senha']",
    "input[aria-label*='Senha']",
]

out_lines = []

out_lines.append(f'Using profile: {profile_dir}')

try:
    with sync_playwright() as p:
        out_lines.append('starting playwright')
        # persistent context to use saved profile
        ctx = p.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=False)
        page = ctx.new_page()
        url = base.rstrip('/') + '/painel'
        out_lines.append(f'navigating to {url}')
        page.goto(url, wait_until='networkidle', timeout=60000)
        time.sleep(4)

        # function to probe selectors
        def probe(sel):
            try:
                el = page.query_selector(sel)
                if not el:
                    return None
                attr = page.evaluate("(el) => el.getAttribute('value')", el)
                prop = page.evaluate("(el) => el.value", el)
                outer = page.evaluate("(el) => el.outerHTML", el)
                return {'selector': sel, 'attr_value': attr, 'prop_value': prop, 'outerHTML': outer[:1000]}
            except Exception as e:
                return {'selector': sel, 'error': str(e)}

        out_lines.append('--- username probes ---')
        found_username = None
        for s in selectors_username:
            r = probe(s)
            out_lines.append(str(r))
            if r and r.get('prop_value'):
                found_username = r
        out_lines.append('--- password probes ---')
        found_password = None
        for s in selectors_password:
            r = probe(s)
            out_lines.append(str(r))
            if r and r.get('prop_value'):
                found_password = r

        # also list all inputs and their types
        out_lines.append('--- all inputs ---')
        inputs = page.query_selector_all('input')
        for i, inp in enumerate(inputs):
            try:
                t = page.evaluate("(el) => el.type", inp)
                n = page.evaluate("(el) => el.name", inp)
                ph = page.evaluate("(el) => el.placeholder", inp)
                val = page.evaluate("(el) => el.value", inp)
                out_lines.append(f'input[{i}] type={t!r} name={n!r} placeholder={ph!r} value={val!r}')
            except Exception as e:
                out_lines.append(f'input[{i}] probe error: {e}')

        # check storage for saved keys
        try:
            local = page.evaluate("() => JSON.stringify(window.localStorage, null, 2)")
            session = page.evaluate("() => JSON.stringify(window.sessionStorage, null, 2)")
            out_lines.append('localStorage keys:')
            out_lines.append(local[:4000])
            out_lines.append('sessionStorage keys:')
            out_lines.append(session[:4000])
        except Exception as e:
            out_lines.append('storage probe failed: ' + str(e))

        # finalize
        out_lines.append('closing context')
        time.sleep(1)
        ctx.close()

except Exception as e:
    out_lines.append('exception: ' + str(e))
    out_lines.append(traceback.format_exc())

# print results
print('\n'.join(out_lines))
# also write to file
try:
    with open('inspect_profile_fields_out.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines))
except Exception:
    pass
