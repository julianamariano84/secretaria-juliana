"""Assistant layer to manage conversation as a virtual helper.

Keeps it safe: works without OpenAI (uses heuristics), but can use
services.openai_client when configured to craft a warmer greeting.
"""
from typing import Dict, Any, List, Optional
import os
import re

try:
    from services.openai_client import generate_greeting_and_action, local_extract_registration_fields
except Exception:
    generate_greeting_and_action = None  # type: ignore
    local_extract_registration_fields = None  # type: ignore

try:
    from webhook.registrations import get_pending
except Exception:
    get_pending = None  # type: ignore


def _next_missing_question(rec: Dict[str, Any]) -> Optional[str]:
    qmap = {
        'name': 'Qual seu nome completo?',
        'dob': 'Qual sua data de nascimento (dd/mm/aaaa)?',
        'cpf': 'Qual seu CPF?',
        'address': 'Qual seu endereço?',
        'confirm': 'Você confirma que deseja se cadastrar? (sim/não)'
    }
    for q in rec.get('questions', []) or []:
        if q not in (rec.get('answers') or {}):
            return qmap.get(q)
    return None


def _is_smalltalk(text: str) -> bool:
    t = (text or '').strip().lower()
    if not t:
        return False
    return bool(re.search(r"\b(oi|ol[aá]|ola|bom dia|boa tarde|boa noite|tudo bem|td bem|obrigad[ao])\b", t))


def handle_user_message(phone: str, text: str, first_contact: bool = False) -> Dict[str, Any]:
    """Return messages to send given the current registration state.

    Strategy:
    - If smalltalk or generic greeting: send a warm greeting and restate the next needed question.
    - If we can extract all registration fields locally, suggest confirmation.
    - Otherwise do nothing (let the default question flow handle it).
    """
    messages: List[str] = []

    rec = get_pending(phone) if get_pending else None
    next_q = _next_missing_question(rec or {}) if rec else None

    # Smalltalk path: warm greeting + restate next question (if any)
    if _is_smalltalk(text):
        greet = None
        if generate_greeting_and_action:
            try:
                ga = generate_greeting_and_action(text, first_contact=first_contact)
                greet = isinstance(ga, dict) and ga.get('greeting')
            except Exception:
                greet = None
        if not greet:
            name = os.getenv('SECRETARY_NAME', 'Márcia')
            title = os.getenv('SECRETARY_TITLE', 'secretária da fonoaudióloga Juliana Mariano')
            greet = f"Olá! Eu sou a {name}, {title}. Vou te ajudar com carinho."

        if next_q:
            messages.append(f"{greet} {next_q}")
        else:
            messages.append(greet)

        return {"messages": messages}

    # If local extractor finds everything, move to confirmation tone
    if local_extract_registration_fields:
        try:
            parsed = local_extract_registration_fields(text)
            if parsed and all(k in parsed and parsed.get(k) for k in ('name', 'dob', 'cpf', 'address')):
                nm = parsed.get('name') or ''
                messages.append(f"Perfeito{(' ' + nm) if nm else ''}! Recebi seus dados. Você confirma o cadastro? (sim/não)")
                return {"messages": messages}
        except Exception:
            pass

    return {"messages": messages}
