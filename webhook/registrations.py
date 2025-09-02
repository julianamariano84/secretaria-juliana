"""Simple file-backed store for pending patient registrations.

Provides helper functions to create a pending registration for a phone
and to append incoming answers. This is intentionally minimal and
designed for local development. A production implementation should use
a proper database and concurrency-safe operations.
"""
from typing import Optional, Dict, Any, List
import json
import os
import time
from pathlib import Path

STORE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
STORE_FILE = os.path.join(STORE_DIR, 'registrations.json')


def _ensure_store() -> None:
    if not os.path.isdir(STORE_DIR):
        try:
            os.makedirs(STORE_DIR, exist_ok=True)
        except Exception:
            pass
    if not os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
        except Exception:
            pass


def _read_all() -> List[Dict[str, Any]]:
    _ensure_store()
    try:
        with open(STORE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _write_all(items: List[Dict[str, Any]]) -> None:
    _ensure_store()
    tmp = STORE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    try:
        os.replace(tmp, STORE_FILE)
    except Exception:
        try:
            os.remove(STORE_FILE)
        except Exception:
            pass
        os.replace(tmp, STORE_FILE)


def _find_by_phone(items: List[Dict[str, Any]], phone: str) -> Optional[Dict[str, Any]]:
    if not phone:
        return None
    for it in items:
        if it.get('phone') == phone:
            return it
    return None


def create_pending(phone: str, name_hint: Optional[str] = None, initiated_by: str = 'outbound') -> Dict[str, Any]:
    """Create a new pending registration entry for `phone` or return existing."""
    items = _read_all()
    existing = _find_by_phone(items, phone)
    if existing:
        return existing

    now = int(time.time())
    questions = [
        'name',
        'dob',
        'cpf',
        'address',
        'confirm'
    ]
    rec = {
        'phone': phone,
        'name_hint': name_hint,
        'created_at': now,
        'status': 'pending',
        'initiated_by': initiated_by,
        'questions': questions,
        'answers': {},
        'history': [],
    # greeting control to avoid repeated greetings
    'greeting_sent': False,
    'greeting_sent_at': None,
        # payment info: will store provider id, url and status when payment created
        'payment': None,
        # scheduling info for Terapee integration
        'scheduling': {
            'status': 'idle',  # idle | awaiting_time | requested | booked | failed
            'requested': None,  # {start_iso, end_iso}
            'result': None,     # booking result or error
        },
    }
    items.append(rec)
    _write_all(items)
    return rec


def append_response(phone: str, text: str, ts: Optional[int] = None) -> Dict[str, Any]:
    """Append an incoming response to the pending registration for phone.

    If no pending registration exists, a new one (initiated_by='inbound') is
    created. Returns the updated registration record.
    """
    if not phone:
        raise ValueError('phone required')
    ts = ts or int(time.time())
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        rec = create_pending(phone, name_hint=None, initiated_by='inbound')
        items = _read_all()  # reload
        rec = _find_by_phone(items, phone)

    # record history (avoid duplicating identical consecutive entries)
    hist = rec.setdefault('history', [])
    if not hist or hist[-1].get('text') != text:
        hist.append({'ts': ts, 'text': text})

    # attempt to fill next unanswered question using heuristics
    # Do not treat the last asked question itself as an answer.
    last_asked = None
    try:
        # infer last question we asked from previous history entry if it matches known prompts
        prompts = {
            'name': 'Qual seu nome completo?',
            'dob': 'Qual sua data de nascimento (dd/mm/aaaa)?',
            'cpf': 'Qual seu CPF?',
            'address': 'Qual seu endereço?',
            'confirm': 'Você confirma que deseja se cadastrar? (sim/não)'
        }
        if len(hist) >= 2:
            prev_text = hist[-2].get('text')
            for key, prompt in prompts.items():
                if prev_text == prompt:
                    last_asked = key
                    break
        # Fallback: use persisted last_sent_question when available, in case
        # another message (ex.: auto-resposta do provedor) veio entre a pergunta
        # e a resposta do usuário.
        if not last_asked:
            try:
                last_q = rec.get('last_sent_question')
                if last_q:
                    for key, prompt in prompts.items():
                        if last_q == prompt:
                            last_asked = key
                            break
            except Exception:
                pass
    except Exception:
        last_asked = None

    for q in rec.get('questions', []):
        if q not in rec.get('answers', {}):
            # if the user only echoed the question, don't store as answer
            if last_asked == q and text.strip() in (prompts.get(q),):
                break
            rec.setdefault('answers', {})[q] = text
            break

    # If confirm question present and answered with a yes-like value, mark confirmed
    answers = rec.get('answers', {})
    if all(k in answers for k in rec.get('questions', [])):
        # all questions answered
        rec['status'] = 'complete'
        rec['completed_at'] = ts
    else:
        # still pending
        rec['status'] = 'pending'

    # persist
    # replace existing record in items
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec


def get_pending(phone: str) -> Optional[Dict[str, Any]]:
    items = _read_all()
    return _find_by_phone(items, phone)


def list_pending() -> List[Dict[str, Any]]:
    return _read_all()


def get_last_history(phone: str) -> Optional[Dict[str, Any]]:
    """Return the last history entry {'ts': int, 'text': str} for phone, if any."""
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return None
    hist = rec.get('history') or []
    if not hist:
        return None
    return hist[-1]


def get_last_sent_question(phone: str) -> Optional[str]:
    """Return the last question text we sent to this phone, if persisted."""
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return None
    return rec.get('last_sent_question')


def set_last_sent_question(phone: str, question: str) -> Optional[Dict[str, Any]]:
    """Persist the last question text we sent for this phone (cross-process dedupe)."""
    if not phone or not question:
        return None
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        # create minimal record if missing
        rec = create_pending(phone)
        items = _read_all()
        rec = _find_by_phone(items, phone)
    rec['last_sent_question'] = question
    rec['last_sent_at'] = int(time.time())
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec


def get_last_outbound(phone: str) -> Optional[Dict[str, Any]]:
    """Return last outbound message record {'ts': int, 'text': str} for phone, if any."""
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return None
    out = rec.get('last_outbound')
    if isinstance(out, dict) and 'text' in out:
        return out
    # backward compat: derive from last_sent_question if present
    if rec.get('last_sent_question'):
        return {'ts': rec.get('last_sent_at') or 0, 'text': rec.get('last_sent_question')}
    return None


def set_last_outbound(phone: str, text: str) -> Optional[Dict[str, Any]]:
    """Persist last outbound message text and timestamp for cross-worker dedupe."""
    if not phone or not text:
        return None
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        rec = create_pending(phone)
        items = _read_all()
        rec = _find_by_phone(items, phone)
    rec['last_outbound'] = {'ts': int(time.time()), 'text': text}
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec


def get_greeting_sent(phone: str) -> bool:
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return False
    return bool(rec.get('greeting_sent'))


def mark_greeting_sent(phone: str) -> Optional[Dict[str, Any]]:
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        rec = create_pending(phone)
        items = _read_all()
        rec = _find_by_phone(items, phone)
    rec['greeting_sent'] = True
    rec['greeting_sent_at'] = int(time.time())
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec


def mark_created(phone: str, created_info: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Mark a pending registration as created and store created_info.

    Returns the updated record or None if not found.
    """
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return None

    rec['status'] = 'created'
    rec['created_at'] = int(time.time())
    rec['created_info'] = created_info or {}

    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break

    _write_all(items)
    return rec


def apply_answers(phone: str, answers: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Merge structured answers into the pending registration for phone.

    Returns the updated registration or None if not found.
    """
    if not phone or not isinstance(answers, dict):
        return None
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        # create pending if missing
        rec = create_pending(phone)
        items = _read_all()
        rec = _find_by_phone(items, phone)

    # merge answers
    rec.setdefault('answers', {}).update({k: v for k, v in answers.items() if v is not None})

    # if all questions answered mark complete
    if all(q in rec.get('answers', {}) for q in rec.get('questions', [])):
        rec['status'] = 'complete'
        rec['completed_at'] = int(time.time())
    else:
        rec['status'] = 'pending'

    # If registration is complete and confirm == True, leave to caller to create payment

    # persist
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec

def extract_and_apply_from_text(phone: str, text: str) -> dict:
    """Try to extract structured answers from a free-text message using OpenAI and apply them."""
    try:
        from services.openai_client import extract_registration_fields
    except Exception:
        extract_registration_fields = None

    if not extract_registration_fields:
        # fallback: append raw response
        return append_response(phone, text)

    parsed = extract_registration_fields(text)
    if not parsed or (isinstance(parsed, dict) and parsed.get('error')):
        # fallback to appending raw response when extraction failed or OpenAI returned an error
        return append_response(phone, text)

    return apply_answers(phone, parsed)


def mark_payment_created(phone: str, payment_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return None
    rec['payment'] = payment_info
    # persist
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec


def mark_payment_confirmed(phone: str, payment_status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return None
    rec.setdefault('payment', {})['status'] = payment_status
    rec['status'] = 'created'
    rec['created_at'] = int(time.time())
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec


def set_scheduling_status(phone: str, status: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    items = _read_all()
    rec = _find_by_phone(items, phone)
    if not rec:
        return None
    sch = rec.setdefault('scheduling', {})
    sch['status'] = status
    if payload:
        if status == 'requested':
            sch['requested'] = payload
        else:
            sch['result'] = payload
    for i, it in enumerate(items):
        if it.get('phone') == phone:
            items[i] = rec
            break
    _write_all(items)
    return rec
