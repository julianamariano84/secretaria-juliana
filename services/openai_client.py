"""Lightweight OpenAI wrapper for common tasks used by the app.

Uses environment variable OPENAI_API_KEY. If not present, functions raise
RuntimeError or return None so existing flows keep working.
"""
import os
import json
from typing import Optional, Dict, Any, List

try:
    # openai>=1.0.0 exposes a client class
    from openai import OpenAI as OpenAIClient
except Exception:
    OpenAIClient = None


def _require_client():
    """Return a configured OpenAI client instance or raise.

    This constructs a new client per-call using the value of OPENAI_API_KEY.
    Returning a client avoids mutating a global and works when the package
    requires the key at construction time.
    """
    if OpenAIClient is None:
        raise RuntimeError('openai package not installed; pip install openai')
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY not set')
    # construct a client with the key explicitly so behavior is deterministic
    return OpenAIClient(api_key=key)


def extract_registration_fields(text: str) -> Optional[Dict[str, Any]]:
    """Ask the model to extract patient registration fields as JSON.

    Returns dict with possible keys: name, dob, cpf, address, confirm
    or None if extraction fails.
    """
    try:
        client = _require_client()
    except Exception as e:
        print(f"[openai_client] client init error: {e}")
        # fallback to local heuristic extractor when client can't be created
        return local_extract_registration_fields(text)
    prompt = (
        "Extraia dados de cadastro de paciente do texto abaixo e retorne SOMENTE um JSON\n"
        "com as chaves: name, dob, cpf, address, confirm (true/false). Se algum campo\n"
        "não estiver presente, coloque null. Texto:\n\n" + text + "\n\nJSON:"
    )

    try:
        resp = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400,
        )
        # new client returns choices with message.content
        content = resp.choices[0].message.content
        # attempt to parse JSON block
        first_brace = content.find('{')
        if first_brace >= 0:
            content = content[first_brace:]
        return json.loads(content)
    except Exception as e:
        print(f"[openai_client] extraction error: {e}")
        try:
            # show raw response when available for debugging
            print('[openai_client] raw response:', getattr(e, 'http_body', None) or getattr(e, 'args', None))
        except Exception:
            pass
        # fallback to local heuristic extractor when API call fails
        return local_extract_registration_fields(text)


def local_extract_registration_fields(text: str) -> Dict[str, Any]:
    """Lightweight heuristic extractor for registration fields.

    Attempts to find name, dob, cpf, address and a consent boolean using
    regular expressions and simple phrase matching. This is intentionally
    conservative and returns null for fields it cannot confidently parse.
    """
    import re

    def find_cpf(t: str) -> Optional[str]:
        m = re.search(r"(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})", t)
        if m:
            return re.sub(r"\D", "", m.group(0))
        return None

    def find_dob(t: str) -> Optional[str]:
        # dd/mm/yyyy or dd/mm/yy or yyyy-mm-dd
        m = re.search(r"(\d{2}/\d{2}/\d{4}|\d{2}/\d{2}/\d{2}|\d{4}-\d{2}-\d{2})", t)
        if m:
            return m.group(0)
        return None

    def find_address(t: str) -> Optional[str]:
        # try to capture street type, name and optional number and return a
        # normalized 'Street Name, number' form when possible
        # street types common in PT-BR
        # capture multi-word street names (avoid stopping at the first short word)
        # make the name capture greedy so it collects multi-word street names
        street_rx = re.compile(
            r"(?:moro na|moro em|endereço[:\s]*)?\b(rua|av\.?|avenida|alameda|travessa|praça|praca|rodovia|estrada)\b\s+([^,\d\n]{2,200})\s*(?:,?\s*(\d{1,6}))?",
            re.I,
        )
        m = street_rx.search(t)
        if m:
            stype = m.group(1) or ''
            name = m.group(2) or ''
            num = m.group(3)
            stype = stype.strip().rstrip('.')
            # normalize name spacing/casing
            name = ' '.join(name.split()).strip()
            # title-case the name but keep common uppercase letters handled
            name = name.title()
            if num:
                return f"{stype.capitalize()} {name}, {num}"
            return f"{stype.capitalize()} {name}"
        return None

    def find_name(t: str) -> Optional[str]:
        # try explicit phrases first
        m = re.search(r"(meu nome é|nome[:\s])\s*([A-ZÀ-Ú][A-Za-zÀ-ú]+(?:\s+[A-ZÀ-Ú][A-Za-zÀ-ú]+){0,4})", t, re.I)
        if m:
            return m.group(2).strip()
        # fallback: take first capitalized sequence of words (naive)
        m2 = re.search(r"\b([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){0,3})\b", t)
        if m2:
            return m2.group(1).strip()
        return None

    def find_confirm(t: str) -> Optional[bool]:
        if re.search(r"\b(confirmo|confirmado|confirmar|sim|ok|autorizo)\b", t, re.I):
            return True
        if re.search(r"\b(não|nao|recuso|negado)\b", t, re.I):
            return False
        return None

    def normalize_cpf(raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 11:
            return None
        # validate checksum
        def is_valid_cpf(d: str) -> bool:
            # invalid if all digits equal
            if d == d[0] * len(d):
                return False
            try:
                nums = [int(x) for x in d]
            except Exception:
                return False
            # first check digit
            s = sum([nums[i] * (10 - i) for i in range(9)])
            r = s % 11
            d1 = 0 if r < 2 else 11 - r
            if d1 != nums[9]:
                return False
            # second check digit
            s2 = sum([nums[i] * (11 - i) for i in range(10)])
            r2 = s2 % 11
            d2 = 0 if r2 < 2 else 11 - r2
            if d2 != nums[10]:
                return False
            return True

        if not is_valid_cpf(digits):
            return None
        return digits

    def normalize_date(raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        # try parse dd/mm/yyyy, dd/mm/yy, yyyy-mm-dd
        try:
            # if already yyyy-mm-dd, convert to dd/mm/yyyy
            if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
                y, mo, d = raw.split('-')
                return f"{d}/{mo}/{y}"
            # if dd/mm/yyyy, normalize to same
            m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", raw)
            if m:
                d, mo, y = m.groups()
                return f"{d}/{mo}/{y}"
            # if dd/mm/yy, expand century then return dd/mm/yyyy
            m2 = re.match(r"^(\d{2})/(\d{2})/(\d{2})$", raw)
            if m2:
                d, mo, y2 = m2.groups()
                y = '19' + y2 if int(y2) > 30 else '20' + y2
                return f"{d}/{mo}/{y}"
        except Exception:
            return None
        return None

    extracted: Dict[str, Any] = {
        'name': None,
        'dob': None,
        'cpf': None,
        'address': None,
        'confirm': None,
    }

    try:
        txt = text or ''
        raw_cpf = find_cpf(txt)
        extracted['cpf'] = normalize_cpf(raw_cpf) if raw_cpf else None
        raw_dob = find_dob(txt)
        extracted['dob'] = normalize_date(raw_dob) if raw_dob else None
        extracted['address'] = find_address(txt)
        extracted['name'] = find_name(txt)
        extracted['confirm'] = find_confirm(txt)
    except Exception as _:
        pass

    return extracted


def generate_registration_questions(context: Optional[str] = None) -> Optional[List[str]]:
    """Ask model to generate a short list of questions to complete registration.

    Returns list of question strings or None on failure.
    """
    try:
        client = _require_client()
    except Exception as e:
        print(f"[openai_client] client init error: {e}")
        return {"error": str(e)}
    prompt = "Gere 5 perguntas curtas para coletar nome completo, data de nascimento, CPF, endereço e consentimento para cadastro."
    if context:
        prompt = context + "\n\n" + prompt

    try:
        resp = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        content = resp.choices[0].message.content
        # split into lines and return non-empty
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        return lines[:6]
    except Exception as e:
        print(f"[openai_client] generation error: {e}")
        try:
            print('[openai_client] raw response:', getattr(e, 'http_body', None) or getattr(e, 'args', None))
        except Exception:
            pass
        return {"error": str(e)}
