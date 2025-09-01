"""Scraper-based scaffold for Terapee UI automation.

This module provides a safe, testable scaffold for UI automation using a
browser automation tool (Playwright recommended). It intentionally does not
execute any browser code unless the instance is configured and Playwright is
installed. When not configured it runs in "stub mode" so unit tests and local
development don't require credentials.

Usage:
  from scheduler.terapee_scraper import TerapeeScraper
  s = TerapeeScraper()
  s.login(username, password)  # optional, will use env vars
  s.check_availability(...)

Note: this scaffold avoids binding to Playwright in tests; implement the
`_run_playwright_flow` method when you're ready to perform real automation.
"""

from typing import Optional, Dict, Any
import os
import re
import time
from dotenv import load_dotenv
from contextlib import contextmanager

# load .env for processes that run the scraper directly
load_dotenv()

try:
    from services.openai_client import generate_registration_questions
except Exception:
    generate_registration_questions = None


class TerapeeScraper:
    """Playwright-backed scraper for Terapee UI automation.

    Behavior:
    - If `TERAPEE_BASE_URL`, `TERAPEE_UI_USER` and `TERAPEE_UI_PASS` are not
      present the class operates in stub mode and returns deterministic results
      (safe for tests).
    - Playwright is imported lazily only when a real flow is executed. If it's
      not installed a clear RuntimeError will be raised with install steps.
    - The scraper supports simple configurable URLs/selectors through env vars
      to avoid hard-coding brittle selectors in code.
    """

    def __init__(self, base_url: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None, headless: bool = True):
        self.base_url = base_url or os.getenv("TERAPEE_BASE_URL")  # e.g. https://app.terapee.com.br
        self.username = username or os.getenv("TERAPEE_UI_USER")
        self.password = password or os.getenv("TERAPEE_UI_PASS")
        self.headless = headless
        # internal runtime objects (playwright, browser, context, page)
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def _ensure_playwright(self):
        """Lazy import and start Playwright components.

        Raises a helpful error if Playwright is not installed.
        """
        if self._playwright:
            return
        try:
            print("[terapee_scraper] importing playwright.sync_api")
            from playwright.sync_api import sync_playwright
            print("[terapee_scraper] starting sync_playwright")
            self._playwright = sync_playwright().start()

            # Check for a requested profile directory (env var TERAPEE_PROFILE_DIR)
            profile_dir = os.getenv("TERAPEE_PROFILE_DIR") or os.getenv("PROFILE_DIR")
            if not profile_dir:
                # fallback default Chrome profile on Windows
                if os.name == 'nt':
                    local = os.getenv('LOCALAPPDATA')
                    if local:
                        possible = os.path.join(local, 'Google', 'Chrome', 'User Data', 'Default')
                        if os.path.isdir(possible):
                            profile_dir = possible

            if profile_dir:
                print(f"[terapee_scraper] launching persistent context with profile: {profile_dir}")
                # launch a persistent context which reuses user profile (cookies, localStorage)
                try:
                    self._context = self._playwright.chromium.launch_persistent_context(user_data_dir=profile_dir, headless=self.headless, channel="chrome")
                    # persistent_context already has pages; reuse the first one
                    pages = self._context.pages
                    self._page = pages[0] if pages else self._context.new_page()
                    self._browser = None
                    print("[terapee_scraper] persistent context ready")
                    return
                except Exception as e_pc:
                    print(f"[terapee_scraper] persistent context launch failed: {e_pc}; falling back to default launch")

            print("[terapee_scraper] launching browser")
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            print("[terapee_scraper] creating context and page")
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            print("[terapee_scraper] browser ready")
        except Exception as e:
            # make the error message explicit and include environment clues
            raise RuntimeError(f"Playwright startup failed: {e}. Make sure browsers are installed (python -m playwright install) and dependencies are available.") from e

    def _query_selector_with_frames(self, selector: str, timeout: int = 2000):
        """Try to find selector on the main page first, then search frames.

        Returns a tuple (element_handle, frame) where frame is None for main page,
        or the Frame object where the element was found.
        """
        page = self._page
        try:
            el = page.query_selector(selector)
            if el:
                return el, None
        except Exception:
            pass

        # try frames
        try:
            for f in page.frames:
                try:
                    el = f.query_selector(selector)
                    if el:
                        return el, f
                except Exception:
                    continue
        except Exception:
            pass

        return None, None

    def _wait_for_selector(self, selector: str, total_wait_ms: int = 10000, poll_ms: int = 500):
        """Retry querying selector across main page and frames until timeout.

        Returns (element_handle, frame) or (None, None).
        """
        page = self._page
        waited = 0
        while waited <= total_wait_ms:
            try:
                el, frm = self._query_selector_with_frames(selector)
                if el:
                    return el, frm
            except Exception:
                pass
            try:
                page.wait_for_timeout(poll_ms)
            except Exception:
                import time
                time.sleep(poll_ms / 1000.0)
            waited += poll_ms
        return None, None

    def close(self):
        """Clean up browser resources if they were created."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        finally:
            self._playwright = None
            self._browser = None
            self._context = None
            self._page = None

    def login(self) -> bool:
        """Perform login against the Terapee UI.

        Uses a best-effort approach to locate common email/password fields and
        submit buttons. For reliability provide explicit selectors via env:
        - TERAPEE_SELECTOR_USERNAME
        - TERAPEE_SELECTOR_PASSWORD
        - TERAPEE_SELECTOR_LOGIN_BUTTON

        Returns True on success. Raises RuntimeError on failure.
        """
        if not self.configured:
            return True

        # lazy-start Playwright
        try:
            print("[terapee_scraper] starting Playwright")
            self._ensure_playwright()
            page = self._page
            login_url = os.getenv("TERAPEE_LOGIN_URL") or f"{self.base_url.rstrip('/')}/painel"
            print(f"[terapee_scraper] navigating to {login_url}")
            try:
                page.goto(login_url, wait_until="load", timeout=10000)
                print("[terapee_scraper] navigation complete")
                try:
                    open("terapee_nav_marker.txt", "w").write("nav-ok")
                    page.screenshot(path="terapee_nav_after_goto.png")
                    print("[terapee_scraper] wrote marker and screenshot after goto")
                except Exception as e_marker:
                    print(f"[terapee_scraper] failed to write marker/screenshot: {e_marker}")
            except Exception as e:
                print(f"[terapee_scraper] navigation error: {e}")
                try:
                    # attempt to capture HTML and screenshot for debugging
                    html = page.content()
                    open("terapee_nav_debug.html", "w", encoding="utf-8").write(html)
                    screenshot_path = "terapee_nav_debug.png"
                    page.screenshot(path=screenshot_path)
                    print(f"[terapee_scraper] saved debug html to terapee_nav_debug.html and screenshot to {screenshot_path}")
                except Exception as e2:
                    print(f"[terapee_scraper] failed to capture debug artifacts: {e2}")
                # continue; maybe the page partially loaded and selectors are present

            # selectors (env override or sensible defaults)
            # include autocomplete attributes and broader name/placeholder matches
            username_sel = os.getenv("TERAPEE_SELECTOR_USERNAME") or (
                "input[autocomplete=\"username\"], input[autocomplete=\"email\"],"
                "input[name=\"email\"], input[type=\"email\"], input[name=\"username\"],"
                "input[placeholder*=\"E-mail\"], input[placeholder*=\"Email\"], input[aria-label*=\"E-mail\"], input[aria-label*=\"Email\"]"
            )
            password_sel = os.getenv("TERAPEE_SELECTOR_PASSWORD") or (
                "input[autocomplete=\"current-password\"], input[autocomplete=\"new-password\"],"
                "input[type=\"password\"], input[name=\"password\"],"
                "input[placeholder*=\"Senha\"], input[aria-label*=\"Senha\"]"
            )
            login_button_sel = os.getenv("TERAPEE_SELECTOR_LOGIN_BUTTON") or (
                "button[type=submit], button:has-text('Entrar'), button:has-text('Acessar'), button:has-text('Login')"
            )

            # configurable wait (ms)
            total_wait_ms = int(os.getenv("TERAPEE_LOGIN_WAIT_MS", "10000"))
            poll_ms = int(os.getenv("TERAPEE_LOGIN_POLL_MS", "500"))

            def wait_for_selector_in_frames(selector: str):
                """Retry querying selector across main page and frames until timeout."""
                waited = 0
                while waited <= total_wait_ms:
                    el, frm = self._query_selector_with_frames(selector)
                    if el:
                        return el, frm
                    try:
                        # small sleep using page.wait_for_timeout when possible
                        page.wait_for_timeout(poll_ms)
                    except Exception:
                        import time
                        time.sleep(poll_ms / 1000.0)
                    waited += poll_ms
                return None, None

            # helper: try label-based heuristics for friendly names
            def try_label_texts(texts):
                # build a combined selector that looks for label-text related inputs and direct aria/placeholder matches
                parts = []
                for t in texts:
                    # label containing text -> input descendant / adjacent
                    parts.append(f"label:has-text(\"{t}\") input")
                    parts.append(f"label:has-text(\"{t}\") + input")
                    parts.append(f"label:has-text(\"{t}\") ~ input")
                    parts.append(f"input[aria-label*=\"{t}\"]")
                    parts.append(f"input[placeholder*=\"{t}\"]")
                combined = ", ".join(parts)
                return wait_for_selector_in_frames(combined)

            # find and fill username with retries
            print(f"[terapee_scraper] attempting to locate username field (wait up to {total_wait_ms}ms)")
            try:
                el_u, frm = wait_for_selector_in_frames(username_sel)
                if el_u:
                    try:
                        el_u.fill(self.username)
                        print(f"[terapee_scraper] filled username (frame={'main' if frm is None else 'frame'})")
                    except Exception as e_fill:
                        print(f"[terapee_scraper] error filling username element: {e_fill}")
                else:
                    print("[terapee_scraper] username selector not found; trying generic input fallback")
                    el = page.query_selector("input[type='text'], input[type='email'], input")
                    if el:
                        try:
                            el.fill(self.username)
                            print("[terapee_scraper] filled username via generic input")
                        except Exception as e_fill:
                            print(f"[terapee_scraper] generic input fill failed: {e_fill}")
            except Exception as e_qs:
                print(f"[terapee_scraper] error searching for username selector: {e_qs}")

            # find and fill password with retries
            print(f"[terapee_scraper] attempting to locate password field (wait up to {total_wait_ms}ms)")
            try:
                el_p, frm_p = wait_for_selector_in_frames(password_sel)
                if el_p:
                    try:
                        el_p.fill(self.password)
                        print(f"[terapee_scraper] filled password (frame={'main' if frm_p is None else 'frame'})")
                        # try pressing Enter immediately after filling password to submit the form
                        try:
                            el_p.press("Enter")
                            print("[terapee_scraper] pressed Enter on password input to submit")
                        except Exception as e_enter:
                            print(f"[terapee_scraper] pressing Enter on password failed: {e_enter}")
                    except Exception as e_fillp:
                        print(f"[terapee_scraper] error filling password element: {e_fillp}")
                else:
                    print("[terapee_scraper] password selector not found in frames; trying direct page query")
                    el_p = page.query_selector(password_sel)
                    if el_p:
                        try:
                            el_p.fill(self.password)
                            print("[terapee_scraper] filled password via direct query")
                        except Exception as e_fillp:
                            print(f"[terapee_scraper] direct password fill failed: {e_fillp}")
                    else:
                        # raise to notify caller that password input wasn't found
                        raise RuntimeError("Password input not found; please provide TERAPEE_SELECTOR_PASSWORD")
            except Exception as e_pass:
                print(f"[terapee_scraper] error searching for password selector: {e_pass}")
                raise

            # click or submit
            print(f"[terapee_scraper] locating login button (wait up to {total_wait_ms}ms)")
            try:
                btn, frm_b = wait_for_selector_in_frames(login_button_sel)
                if btn:
                    try:
                        print(f"[terapee_scraper] clicking login button (frame={'main' if frm_b is None else 'frame'})")
                        btn.click()
                    except Exception as e_click:
                        print(f"[terapee_scraper] click failed: {e_click}; attempting Enter on password field")
                        try:
                            el_p.press("Enter")
                        except Exception as e_press:
                            print(f"[terapee_scraper] pressing Enter failed: {e_press}")
                else:
                    print("[terapee_scraper] login button not found; attempting Enter on last field")
                    try:
                        el_p.press("Enter")
                    except Exception as e_press:
                        print(f"[terapee_scraper] pressing Enter failed: {e_press}")
                # extra fallback: clickable text element (some sites use div/text for submit)
                try:
                    if not (page.query_selector('text=Agenda') or page.query_selector('text=Dashboard')):
                        # try clicking a visible element with the text 'Entrar'
                        try:
                            el_text = page.locator("text=Entrar").first
                            if el_text and el_text.is_visible():
                                print('[terapee_scraper] clicking text element "Entrar" as fallback')
                                try:
                                    el_text.click()
                                except Exception as e_text_click:
                                    print(f"[terapee_scraper] click of text=Entrar failed: {e_text_click}")
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception as e_btn:
                print(f"[terapee_scraper] error locating/clicking login button: {e_btn}")

            # wait after submit for dashboard or network idle
            final_wait_ms = int(os.getenv("TERAPEE_POST_LOGIN_WAIT_MS", "12000"))
            try:
                page.wait_for_load_state("networkidle", timeout=final_wait_ms)
                print("[terapee_scraper] load state reached after submit")
            except Exception:
                # tolerate timeout; continue to heuristic checks
                print("[terapee_scraper] networkidle wait timed out; continuing to heuristics")

            # heuristic: check if login succeeded by searching for common dashboard markers
            try:
                if page.query_selector("text=Agenda") or page.query_selector("text=Dashboard"):
                    print("[terapee_scraper] detected dashboard marker (Agenda/Dashboard)")
                    return True
            except Exception:
                pass

            # if nothing decisive, return True but caller should validate access
            print("[terapee_scraper] login flow finished without explicit marker; returning True (caller should validate)")
            return True
        except Exception as e:
            # close browser resources to avoid leaks
            try:
                self.close()
            finally:
                raise RuntimeError(f"Login failed: {e}") from e

    def check_availability(self, professional_id: str, start_iso: str, end_iso: str, service_id: Optional[str] = None, timezone: Optional[str] = None) -> Dict[str, Any]:
        """Check availability using UI automation.

        Configurable env vars:
        - TERAPEE_AVAILABILITY_URL: if provided, this URL will be opened. It may
          contain placeholders {professional_id},{start_iso},{end_iso} which
          will be replaced.
        - TERAPEE_AVAILABILITY_OK_REGEX: regex that, if matched on the page
          content, indicates availability (default looks for words like
          "Disponível"/"Livre").

        Returns normalized dict {available: bool, reasons: [str]}.
        """
        if not self.configured:
            return {"available": True, "reasons": ["stub mode: assume free"]}

        self._ensure_playwright()
        page = self._page

        url_template = os.getenv("TERAPEE_AVAILABILITY_URL") or f"{self.base_url.rstrip('/')}/painel/agenda"
        url = url_template.format(professional_id=professional_id, start_iso=start_iso, end_iso=end_iso, service_id=service_id or "")
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception:
            # continue; page may still render dynamically
            pass

        # Give the SPA some time to render relevant slots
        try:
            page.wait_for_timeout(int(os.getenv("TERAPEE_AVAILABILITY_RENDER_MS", "1500")))
        except Exception:
            pass

        content = page.content()

        ok_regex = os.getenv("TERAPEE_AVAILABILITY_OK_REGEX") or r"(Dispon[ií]vel|Livre|Livre\.|Slot livre)"
        if re.search(ok_regex, content, re.IGNORECASE):
            return {"available": True, "reasons": []}

        # detect busy words
        busy_regex = r"(Ocupad[oa]|Indispon[ií]vel|Agendado)"
        if re.search(busy_regex, content, re.IGNORECASE):
            return {"available": False, "reasons": ["detected busy text"]}

        # As a fallback, try locating a slot element if a selector is provided
        slot_sel = os.getenv("TERAPEE_SELECTOR_AVAIL_SLOT")
        if slot_sel:
            el, frm = self._wait_for_selector(slot_sel, total_wait_ms=int(os.getenv("TERAPEE_AVAIL_SLOT_WAIT_MS", "5000")), poll_ms=500)
            if el:
                return {"available": True, "reasons": [f"found_slot_selector:{slot_sel}"]}

        return {"available": False, "reasons": ["no decisive marker found"]}

    def is_patient_registered(self, patient_name: str) -> bool:
        """Check if a patient is already registered in Terapee UI.

        Heuristic: open the patients page (configurable via TERAPEE_PATIENTS_URL)
        and search for the patient's name in the rendered DOM or by a selector
        `TERAPEE_SELECTOR_PATIENT_ITEM` if provided.
        Returns True when the patient name appears; False otherwise.
        """
        if not self.configured:
            return True

        self._ensure_playwright()
        page = self._page

        patients_url = os.getenv("TERAPEE_PATIENTS_URL") or f"{self.base_url.rstrip('/')}/painel/pacientes"
        try:
            page.goto(patients_url, wait_until="networkidle", timeout=10000)
        except Exception:
            # tolerate and continue to search
            pass

        try:
            page.wait_for_timeout(800)
        except Exception:
            pass

        # direct selector (configurable)
        sel = os.getenv("TERAPEE_SELECTOR_PATIENT_ITEM")
        if sel:
            el, _ = self._wait_for_selector(sel, total_wait_ms=3000, poll_ms=300)
            try:
                if el:
                    text = el.inner_text()
                    if patient_name.lower() in text.lower():
                        return True
            except Exception:
                pass

        # fallback: search page content for the patient name
        try:
            content = page.content()
            if patient_name.lower() in content.lower():
                return True
        except Exception:
            pass

        return False

    def start_patient_registration_via_chat(self, patient_phone: str, patient_name_hint: Optional[str] = None) -> Dict[str, Any]:
        """Initiate patient registration by sending sequential questions via messaging.

        This function only sends questions (outbound); it does not wait for or
        consume replies. It returns a record of the questions sent. The
        messaging worker (or an incoming webhook) should collect responses and
        complete the registration later.
        """
        if not patient_phone:
            return {"sent": False, "error": "no_phone"}

        # lazy import of messaging sender to avoid heavy deps at module import
        try:
            from messaging.sender import send_text
        except Exception:
            # messaging not available; return structured failure
            return {"sent": False, "error": "messaging_unavailable"}
        
        # Load configurable questions from env var TERAPEE_REG_QUESTIONS.
        # Format: newline-separated questions. If not set, use sensible defaults.
        raw = os.getenv('TERAPEE_REG_QUESTIONS')
        if raw:
            questions = [q.strip() for q in raw.splitlines() if q.strip()]
        else:
            clinic = os.getenv('CLINIC_NAME') or 'Nossa clínica'
            questions = [
                f"Olá! Aqui é {clinic}. Vamos finalizar seu cadastro para agendar sua consulta.",
                "1) Por favor, confirme seu nome completo.",
                "2) Qual a sua data de nascimento? (DD/MM/AAAA)",
                "3) Qual o seu CPF? (só números ou no formato 000.000.000-00)",
                "4) Qual seu endereço (rua, número, bairro) — opcional, responda 'pular' para ignorar.",
                "5) Você autoriza que registremos seus dados no sistema para fins de atendimento? Responda SIM ou NÃO.",
            ]

            # Prefer OpenAI-generated questions when available, else use env var or defaults
            questions = None
            if generate_registration_questions:
                try:
                    questions = generate_registration_questions(patient_name_hint)
                except Exception:
                    questions = None

            if not questions:
                # Load configurable questions from env var TERAPEE_REG_QUESTIONS.
                # Format: newline-separated questions. If not set, use sensible defaults.
                raw = os.getenv('TERAPEE_REG_QUESTIONS')
                if raw:
                    questions = [q.strip() for q in raw.splitlines() if q.strip()]
                else:
                    clinic = os.getenv('CLINIC_NAME') or 'Nossa clínica'
                    questions = [
                        f"Olá! Aqui é {clinic}. Vamos finalizar seu cadastro para agendar sua consulta.",
                        "1) Por favor, confirme seu nome completo.",
                        "2) Qual a sua data de nascimento? (DD/MM/AAAA)",
                        "3) Qual o seu CPF? (só números ou no formato 000.000.000-00)",
                        "4) Qual seu endereço (rua, número, bairro) — opcional, responda 'pular' para ignorar.",
                        "5) Você autoriza que registremos seus dados no sistema para fins de atendimento? Responda SIM ou NÃO.",
                    ]

        # If we have a name hint, insert a friendly confirmation early
        if patient_name_hint:
            questions.insert(1, f"Recebemos parcialmente o nome: {patient_name_hint}. Está correto? Se não, envie o nome completo.")

        sent = []
        for q in questions:
            try:
                res = send_text(patient_phone, q)
                sent.append({"question": q, "result": res})
            except Exception as e:
                sent.append({"question": q, "error": str(e)})

        # After questions, send a short confirmation/instruction message
        confirmation = os.getenv('TERAPEE_REG_CONFIRMATION') or (
            "Obrigado — suas respostas foram registradas. Assim que recebermos todas, retornaremos com a confirmação do cadastro e do agendamento."
        )
        try:
            conf_res = send_text(patient_phone, confirmation)
            sent.append({"question": "__confirmation__", "result": conf_res})
        except Exception as e:
            sent.append({"question": "__confirmation__", "error": str(e)})

        return {"sent": True, "phone": patient_phone, "questions": sent}

    def create_patient_from_registration(self, registration: dict) -> Dict[str, Any]:
        """Attempt to create a patient in Terapee using a completed registration.

        registration: record produced by `webhook.registrations` with keys
        'phone' and 'answers'. Returns a dict describing the result.
        In stub mode this returns a synthetic created_id.
        """
        if not registration or not isinstance(registration, dict):
            return {"created": False, "error": "invalid_registration"}

        phone = registration.get('phone')
        answers = registration.get('answers', {})

        # build payload from answers heuristics and normalize
        try:
            from utils.normalizers import normalize_phone, normalize_date, normalize_cpf
        except Exception:
            normalize_phone = lambda x: x
            normalize_date = lambda x: x
            normalize_cpf = lambda x: x

        payload = {
            'name': answers.get('name') or registration.get('name_hint'),
            'dob': normalize_date(answers.get('dob')) or answers.get('dob'),
            'cpf': normalize_cpf(answers.get('cpf')) or answers.get('cpf'),
            'address': answers.get('address'),
            'phone': normalize_phone(phone) or phone,
        }

        if not self.configured:
            # stub create
            created_id = f"stub-patient-{int(time.time())}"
            return {"created": True, "patient_id": created_id, "payload": payload}

        # Real creation via UI: open patients page and try to fill the create form.
        try:
            self._ensure_playwright()
            page = self._page
            patients_url = os.getenv('TERAPEE_PATIENTS_URL') or f"{self.base_url.rstrip('/')}/painel/pacientes"
            try:
                page.goto(patients_url, wait_until='networkidle')
            except Exception:
                pass

            # wait for UI
            try:
                page.wait_for_timeout(800)
            except Exception:
                pass

            # heuristics for opening "Cadastrar paciente" button
            for sel in ["text=Cadastrar paciente", "text=Novo paciente", "button:has-text('Cadastrar')", "button:has-text('Novo')"]:
                el, _ = self._wait_for_selector(sel, total_wait_ms=800, poll_ms=200)
                if el:
                    try:
                        el.click()
                        break
                    except Exception:
                        continue

            # attempt to fill fields using heuristics
            def try_fill_any(variants, value):
                for v in variants:
                    try:
                        if self._wait_for_selector(v, total_wait_ms=600, poll_ms=200)[0]:
                            try:
                                page.fill(v, value)
                                return True
                            except Exception:
                                try:
                                    page.click(v)
                                    page.fill(v, value)
                                    return True
                                except Exception:
                                    continue
                    except Exception:
                        continue
                return False

            try_fill_any(["input[placeholder*='Nome']", "input[name*='name']", "input[aria-label*='Nome']"], payload['name'] or '')
            try_fill_any(["input[placeholder*='Nascimento']", "input[name*='dob']", "input[aria-label*='Nascimento']"], payload['dob'] or '')
            try_fill_any(["input[placeholder*='CPF']", "input[name*='cpf']", "input[aria-label*='CPF']"], payload['cpf'] or '')
            try_fill_any(["input[placeholder*='Telefone']", "input[name*='phone']", "input[aria-label*='Telefone']"], payload['phone'] or '')
            try_fill_any(["input[placeholder*='Endereço']", "input[name*='address']", "input[aria-label*='Endereço']"], payload['address'] or '')

            # try to submit
            for s in ["button:has-text('Salvar')", "button:has-text('Cadastrar')", "text=Salvar"]:
                elb, _ = self._wait_for_selector(s, total_wait_ms=1200, poll_ms=300)
                if elb:
                    try:
                        elb.click()
                        break
                    except Exception:
                        continue

            try:
                page.wait_for_load_state('networkidle', timeout=4000)
            except Exception:
                pass

            # attempt to find a created patient id in DOM
            content = page.content()
            m = re.search(r"patient[_-]?id\W*(?:[:=]\s*|\")\s*(\w+)", content, re.IGNORECASE)
            if m:
                return {"created": True, "patient_id": m.group(1), "payload": payload}

            # otherwise assume success if confirmation text present
            if re.search(r"(Paciente criado|Cadastrado|Salvo)", content, re.IGNORECASE):
                return {"created": True, "patient_id": None, "payload": payload}

            return {"created": False, "error": "no_confirmation", "payload": payload, "raw": content}
        except Exception as e:
            return {"created": False, "error": str(e), "payload": payload}

    def book_consultation(self, professional_id: str, patient_name: str, start_iso: str, end_iso: str, service_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Book a consultation via UI automation.

        Configurable env vars for booking flow (selectors/URL):
        - TERAPEE_BOOKING_URL: page to open (may contain placeholders)
        - TERAPEE_SELECTOR_BOOK_PROFESSIONAL
        - TERAPEE_SELECTOR_BOOK_PATIENT
        - TERAPEE_SELECTOR_BOOK_START
        - TERAPEE_SELECTOR_BOOK_END
        - TERAPEE_SELECTOR_BOOK_SUBMIT

        Returns normalized dict {success, booking_id, error, raw}.
        """
        if not self.configured:
            return {"success": True, "booking_id": f"stub-{start_iso}", "error": None}

        self._ensure_playwright()
        page = self._page

        url_template = os.getenv("TERAPEE_BOOKING_URL") or f"{self.base_url.rstrip('/')}/painel/agenda/novo"
        url = url_template.format(professional_id=professional_id, start_iso=start_iso, end_iso=end_iso, service_id=service_id or "")
        # Try to navigate via UI first (click Agenda -> Novo) when authenticated
        try:
            ag_el, _ = self._wait_for_selector("text=Agenda", total_wait_ms=3000, poll_ms=300)
            if ag_el:
                try:
                    ag_el.click()
                    try:
                        page.wait_for_timeout(800)
                    except Exception:
                        pass
                    # try to open new booking form via common controls
                    for sel in ["text=Novo", "text=Agendar", "text=Agendamento", "button:has-text('Novo')", "button:has-text('Agendar')"]:
                        el_new, _ = self._wait_for_selector(sel, total_wait_ms=1500, poll_ms=300)
                        if el_new:
                            try:
                                el_new.click()
                                break
                            except Exception:
                                continue
                except Exception:
                    pass
        except Exception:
            pass

        # fallback: open booking URL directly
        try:
            page.goto(url, wait_until="networkidle")
        except Exception:
            pass
        # selectors
        sel_prof = os.getenv("TERAPEE_SELECTOR_BOOK_PROFESSIONAL")
        sel_patient = os.getenv("TERAPEE_SELECTOR_BOOK_PATIENT")
        sel_start = os.getenv("TERAPEE_SELECTOR_BOOK_START")
        sel_end = os.getenv("TERAPEE_SELECTOR_BOOK_END")
        sel_submit = os.getenv("TERAPEE_SELECTOR_BOOK_SUBMIT") or "button[type=submit], button:has-text('Salvar'), button:has-text('Agendar')"

        try:
            # wait briefly for the booking form to render
            try:
                page.wait_for_timeout(int(os.getenv("TERAPEE_BOOKING_RENDER_MS", "800")))
            except Exception:
                pass

            def safe_fill(selector, value, name="field"):
                if not selector:
                    return False
                el, frm = self._wait_for_selector(selector, total_wait_ms=int(os.getenv("TERAPEE_BOOKING_FIELD_WAIT_MS", "4000")), poll_ms=400)
                if el:
                    try:
                        el.fill(value)
                        return True
                    except Exception:
                        try:
                            # try clicking then typing
                            el.click()
                            el.fill(value)
                            return True
                        except Exception:
                            return False
                return False

            def find_and_fill(candidates, value, field_name="field"):
                """Try multiple candidate selectors and dialog-scoped fallbacks.

                candidates: list of selector strings (will be tried in order).
                Returns True when a fill succeeded.
                """
                # try candidates directly first
                for c in candidates:
                    try:
                        if safe_fill(c, value, field_name):
                            print(f"[terapee_scraper] filled {field_name} using selector: {c}")
                            return True
                    except Exception:
                        pass

                # try label-based heuristics inside any open dialog/modal
                dialog_prefixes = ["", "role=dialog ", "[aria-modal=true] "]
                heuristics = []
                # build heuristics from simple variations
                heuristics += [f"label:has-text(\"{field_name}\") input", f"label:has-text(\"{field_name}\") textarea"]
                heuristics += [f"input[placeholder*='{field_name}']", f"input[name*='{field_name}']", f"input[aria-label*='{field_name}']"]
                # try within dialog scopes
                for prefix in dialog_prefixes:
                    for h in heuristics:
                        sel = prefix + h
                        try:
                            if safe_fill(sel, value, field_name):
                                print(f"[terapee_scraper] filled {field_name} using dialog-scoped selector: {sel}")
                                return True
                        except Exception:
                            pass

                # last resort: try any visible input on the page that contains the placeholder/prompt text
                try:
                    for term in [field_name, field_name.capitalize(), field_name.replace('_', ' ')]:
                        el, _ = self._wait_for_selector(f"input[placeholder*='{term}']", total_wait_ms=800, poll_ms=200)
                        if el:
                            try:
                                el.fill(value)
                                print(f"[terapee_scraper] filled {field_name} via last-resort placeholder match: {term}")
                                return True
                            except Exception:
                                continue
                except Exception:
                    pass

                return False

            # try to fill professional/patient/start/end using selectors or heuristic fallbacks
            prof_filled = find_and_fill([sel_prof] if sel_prof else [], professional_id, "profissional")
            patient_filled = find_and_fill([sel_patient] if sel_patient else [], patient_name, "paciente")
            start_filled = find_and_fill([sel_start] if sel_start else [], start_iso, "início")
            end_filled = find_and_fill([sel_end] if sel_end else [], end_iso, "fim")

            # heuristic: if specific selectors not provided, try common name placeholders
            if not prof_filled:
                safe_fill("input[placeholder*='Profissional'], input[name*='prof'], input[aria-label*='Profissional']", professional_id, "prof heuristic")
            if not patient_filled:
                safe_fill("input[placeholder*='Paciente'], input[name*='pacient'], input[aria-label*='Paciente']", patient_name, "patient heuristic")
            if not start_filled:
                safe_fill("input[placeholder*='Início'], input[name*='start'], input[aria-label*='Início']", start_iso, "start heuristic")
            if not end_filled:
                safe_fill("input[placeholder*='Fim'], input[name*='end'], input[aria-label*='Fim']", end_iso, "end heuristic")

            # metadata
            if metadata and isinstance(metadata, dict):
                for k, v in metadata.items():
                    sel = os.getenv(f"TERAPEE_SELECTOR_META_{k.upper()}")
                    if sel:
                        safe_fill(sel, str(v), f"meta_{k}")

            # Before finalizing booking, ensure patient exists. If not, start a chat-driven registration
            try:
                registered = self.is_patient_registered(patient_name)
            except Exception:
                registered = True

            if not registered:
                # determine phone to contact for registration
                phone = None
                if metadata and isinstance(metadata, dict):
                    phone = metadata.get('phone') or metadata.get('telefone') or metadata.get('tel')
                if not phone:
                    phone = os.getenv('DEFAULT_PATIENT_PHONE')

                # start registration flow via messaging and return an actionable result
                reg_result = self.start_patient_registration_via_chat(phone, patient_name_hint=patient_name)
                return {"success": False, "booking_id": None, "error": "patient_not_registered", "registration_started": reg_result}

            # submit: prefer configured submit selector, else try dialog/button text heuristics
            btn, frm = self._wait_for_selector(sel_submit, total_wait_ms=3000, poll_ms=300)
            if btn:
                try:
                    btn.click()
                except Exception:
                    try:
                        page.keyboard.press("Enter")
                    except Exception:
                        pass
            else:
                # try dialog-scoped buttons first
                tried = False
                for s in ["role=dialog button:has-text('Salvar')", "role=dialog button:has-text('Agendar')", "role=dialog button:has-text('Confirmar')", "button:has-text('Salvar')", "button:has-text('Agendar')", "button:has-text('Confirmar')"]:
                    elb, _ = self._wait_for_selector(s, total_wait_ms=1200, poll_ms=300)
                    if elb:
                        tried = True
                        try:
                            elb.click()
                            break
                        except Exception:
                            continue
                if not tried:
                    # try clicking any visible text-based submit
                    try:
                        el_text, _ = self._wait_for_selector("text=Salvar, text=Agendar, text=Confirmar", total_wait_ms=2000, poll_ms=300)
                        if el_text:
                            try:
                                el_text.click()
                            except Exception:
                                try:
                                    page.keyboard.press("Enter")
                                except Exception:
                                    pass
                        else:
                            try:
                                page.keyboard.press("Enter")
                            except Exception:
                                pass
                    except Exception:
                        pass

            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # analyze result
            content = page.content()

            # Try to extract booking id from page using common patterns
            m = re.search(r"booking[_-]?id\W*(?:[:=]\s*|\")\s*(\w+)", content, re.IGNORECASE)
            if m:
                return {"success": True, "booking_id": m.group(1), "error": None, "raw": None}

            # If no booking id found, but page seems to show confirmation, return success
            if re.search(r"(Agendado|Confirmado|Salvo|Agendamento realizado)", content, re.IGNORECASE):
                return {"success": True, "booking_id": None, "error": None, "raw": None}

            # Save debug artifacts for troubleshooting
            try:
                open("terapee_booking_debug.html", "w", encoding="utf-8").write(content)
                page.screenshot(path="terapee_booking_debug.png")
            except Exception:
                pass

            return {"success": False, "booking_id": None, "error": "no confirmation found", "raw": content}
        except Exception as e:
            # ensure browser cleaned up but keep for debugging
            try:
                content = page.content()
                open("terapee_booking_exception.html", "w", encoding="utf-8").write(content)
            except Exception:
                pass
            self.close()
            return {"success": False, "booking_id": None, "error": str(e)}

