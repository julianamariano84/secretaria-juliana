"""Envio de mensagens via Z-API (com fallback para stub em dev).

Configurações esperadas no ambiente (.env):

Se as variáveis não estiverem presentes, o módulo cai em um stub local para desenvolvimento.

Observação: quando `CLIENT_TOKEN` estiver configurado, o sender prefere enviar esse valor
no cabeçalho HTTP `Client-Token` junto com o payload {"phone","message"}, pois alguns
endpoints Z-API exigem esse cabeçalho.
"""
"""Envio de mensagens via Z-API com fallback stub.

Esperado no .env:
- ZAPI_URL (ex: https://api.z-api.io/instances/<id>/send-message)
- ZAPI_TOKEN
"""
import os
import json
import logging
import re
import time

log = logging.getLogger(__name__)

# If DEBUG_ZAPI=1 is set, enable debug logging for this module
if os.getenv('DEBUG_ZAPI') == '1':
    # ensure a handler exists so debug output shows when this module is used directly
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter('%(levelname)s:%(name)s: %(message)s'))
        log.addHandler(h)
    log.setLevel(logging.DEBUG)

# keep a small ring buffer of last attempts (masked) for secure debug endpoint
_LAST_DEBUG = {
    'ts': None,
    'attempts': [],  # list of {url, headers, payload, status, body}
}

# short-term in-process dedupe to avoid sending the same text multiple times
# to the same phone due to webhook echoes or retries
_SENT_RECENT = {}

def get_last_debug():
    try:
        return {
            'ts': _LAST_DEBUG.get('ts'),
            'attempts': list(_LAST_DEBUG.get('attempts') or []),
        }
    except Exception:
        return {'ts': None, 'attempts': []}

try:
    import requests
except Exception:
    requests = None

# Try importing cross-worker dedupe helpers; keep optional
try:
    from webhook.registrations import get_last_outbound, set_last_outbound
except Exception:
    get_last_outbound = None
    set_last_outbound = None

ZAPI_URL = os.getenv("ZAPI_URL")
# Prefer the new env name ZAP_TOKEN, fall back to ZAPI_TOKEN for backward compat
ZAPI_TOKEN = os.getenv("ZAP_TOKEN") or os.getenv("ZAPI_TOKEN")
# Optional client token some Z-API instances require
CLIENT_TOKEN = os.getenv("CLIENT_TOKEN") or os.getenv("CLIENTTOKEN") or os.getenv("CLIENT_TOKEN_ID")


def _stub_send(phone: str, message: str) -> dict:
    log.info("[stub] send_text to %s: %s", phone, message)
    return {"to": phone, "message": message, "status": "sent (stub)"}


def send_text(phone: str, message: str) -> dict:
    """Envia texto via Z-API. Se ZAPI_URL e ZAPI_TOKEN não estiverem setados, usa stub.

    Lança RuntimeError em erros de configuração ou falha HTTP.
    """
    # Basic validation
    if not isinstance(phone, str) or not isinstance(message, str):
        raise ValueError("phone e message devem ser strings")

    # Read configuration at call time (allows tests to monkeypatch env)
    local_zapi_url = os.getenv("ZAPI_URL")
    local_zapi_token = os.getenv("ZAP_TOKEN") or os.getenv("ZAPI_TOKEN")
    local_client_token = os.getenv("CLIENT_TOKEN") or os.getenv("CLIENTTOKEN") or os.getenv("CLIENT_TOKEN_ID")

    # Normalize phone early (digits only) for dedupe and policy checks
    clean_phone = re.sub(r"\D", "", phone) if isinstance(phone, str) else phone

    # Policy: optional block/allow lists via env to avoid accidental sends
    try:
        bl_raw = os.getenv('BLOCK_PHONES', '')
        al_raw = os.getenv('ALLOW_PHONES', '')
        block = {re.sub(r"\D", "", p) for p in bl_raw.replace(';', ',').split(',') if p.strip()}
        allow = {re.sub(r"\D", "", p) for p in al_raw.replace(';', ',').split(',') if p.strip()}
    except Exception:
        block, allow = set(), set()
    if isinstance(clean_phone, str):
        # If ALLOW list is set, only send to those; otherwise skip
        if allow and clean_phone not in allow:
            if os.getenv('DEBUG_ZAPI') == '1':
                try:
                    log.debug("Z-API send skipped (allowlist): to=%s not in ALLOW_PHONES", clean_phone)
                    _LAST_DEBUG['ts'] = int(time.time())
                    attempts = _LAST_DEBUG.setdefault('attempts', [])
                    attempts.append({'url': '(skipped-allowlist)', 'headers': {}, 'payload': {'phone': clean_phone, 'message': message}, 'status': 'SKIP', 'body': 'not in ALLOW_PHONES'})
                    if len(attempts) > 5:
                        del attempts[:-5]
                except Exception:
                    pass
            return {"to": clean_phone, "message": message, "status": "skipped_not_allowed"}
        # If phone is in BLOCK list, skip
        if clean_phone in block:
            if os.getenv('DEBUG_ZAPI') == '1':
                try:
                    log.debug("Z-API send skipped (blocklist): to=%s in BLOCK_PHONES", clean_phone)
                    _LAST_DEBUG['ts'] = int(time.time())
                    attempts = _LAST_DEBUG.setdefault('attempts', [])
                    attempts.append({'url': '(skipped-blocklist)', 'headers': {}, 'payload': {'phone': clean_phone, 'message': message}, 'status': 'SKIP', 'body': 'in BLOCK_PHONES'})
                    if len(attempts) > 5:
                        del attempts[:-5]
                except Exception:
                    pass
            return {"to": clean_phone, "message": message, "status": "skipped_blocked"}

    # In-process dedupe: skip if same phone+message was sent very recently
    try:
        ttl = int(os.getenv('ZAPI_SEND_DEDUP_SECONDS', '60'))
    except Exception:
        ttl = 30
    if ttl > 0 and isinstance(clean_phone, str) and isinstance(message, str):
        try:
            now = int(time.time())
            key = (clean_phone, message)
            last = _SENT_RECENT.get(key)
            if last and (now - int(last)) < ttl:
                # record skipped attempt for debug visibility
                if os.getenv('DEBUG_ZAPI') == '1':
                    try:
                        log.debug("Z-API send skipped (dedupe %ss): to=%s message=%s", ttl, clean_phone, message)
                        # minimal record of skip
                        try:
                            def _mask_token(val: str) -> str:
                                if not val:
                                    return None
                                v = str(val)
                                if len(v) <= 6:
                                    return v[:1] + '***' + v[-1:]
                                return v[:3] + '***' + v[-3:]
                            _LAST_DEBUG['ts'] = now
                            attempts = _LAST_DEBUG.setdefault('attempts', [])
                            attempts.append({
                                'url': '(skipped-dedupe)',
                                'headers': {},
                                'payload': {'phone': clean_phone, 'message': message},
                                'status': 'SKIP',
                                'body': f'skipped duplicate within {ttl}s',
                            })
                            if len(attempts) > 5:
                                del attempts[:-5]
                        except Exception:
                            pass
                    except Exception:
                        pass
                return {"to": clean_phone, "message": message, "status": "skipped_duplicate"}
            _SENT_RECENT[key] = now
        except Exception:
            pass

    # Cross-worker dedupe: consult persisted last outbound; skip if identical within TTL
    try:
        ttl = int(os.getenv('ZAPI_SEND_DEDUP_SECONDS', '60'))
    except Exception:
        ttl = 30
    if ttl > 0 and get_last_outbound and isinstance(clean_phone, str):
        try:
            last = get_last_outbound(clean_phone)
            now = int(time.time())
            if last and last.get('text') == message and (now - int(last.get('ts') or 0)) < ttl:
                if os.getenv('DEBUG_ZAPI') == '1':
                    try:
                        log.debug("Z-API send skipped (persist dedupe %ss): to=%s message=%s", ttl, clean_phone, message)
                        _LAST_DEBUG['ts'] = now
                        attempts = _LAST_DEBUG.setdefault('attempts', [])
                        attempts.append({'url': '(skipped-persist)', 'headers': {}, 'payload': {'phone': clean_phone, 'message': message}, 'status': 'SKIP', 'body': f'persist duplicate within {ttl}s'})
                        if len(attempts) > 5:
                            del attempts[:-5]
                    except Exception:
                        pass
                return {"to": clean_phone, "message": message, "status": "skipped_persist_duplicate"}
        except Exception:
            pass

    # If no Z-API config (no URL and no auth at all), fallback to stub
    if not local_zapi_url and not local_zapi_token and not local_client_token:
        res = _stub_send(clean_phone or phone, message)
        if set_last_outbound and isinstance(clean_phone, str):
            try:
                set_last_outbound(clean_phone, message)
            except Exception:
                pass
        return res

    if requests is None:
        raise RuntimeError("Biblioteca 'requests' não está disponível. Instale com pip install requests")

    # Require URL and at least one authentication method (ZAP_TOKEN or CLIENT_TOKEN)
    if not local_zapi_url:
        raise RuntimeError("Z-API parcialmente configurada: defina ZAPI_URL no .env")
    if not (local_zapi_token or local_client_token):
        raise RuntimeError("Z-API parcialmente configurada: defina ZAP_TOKEN (ou CLIENT_TOKEN) no .env")

    # Simplified: single proven request variant only.
    # Build canonical URL ending with /send-text
    preferred = os.getenv('ZAPI_PREFERRED_ENDPOINT')
    if local_zapi_url:
        if '/send-text' in local_zapi_url:
            idx = local_zapi_url.find('/send-text')
            local_zapi_url = local_zapi_url[: idx + len('/send-text')]
        elif '/send-message' in local_zapi_url and preferred == 'send-text':
            idx = local_zapi_url.find('/send-message')
            local_zapi_url = local_zapi_url[: idx] + '/send-text'
        else:
            local_zapi_url = local_zapi_url.rstrip('/') + '/send-text'

    # If the configured URL embeds a token path segment like /token/<TOKEN>/...,
    # ensure it matches ZAP_TOKEN if that env var is set. This avoids a common
    # misconfiguration where the URL token and the env token differ causing
    # 'Instance not found' responses from Z-API.
    try:
        if '/token/' in local_zapi_url:
            # extract the token portion after '/token/' until next '/'
            token_part = local_zapi_url.split('/token/', 1)[1]
            token_in_url = token_part.split('/', 1)[0] if token_part else ''
            if token_in_url and local_zapi_token and token_in_url != local_zapi_token:
                raise RuntimeError(
                    f"Z-API token mismatch: token embedded in ZAPI_URL ('{token_in_url}') "
                    f"does not match ZAP_TOKEN ('{local_zapi_token}'). Remove token from the URL or fix the env var."
                )
    except RuntimeError:
        raise
    except Exception:
        # If parsing fails for any reason, don't mask the original problem;
        # continue and let the request/response provide details.
        pass

    # Build a list of candidate payload and header shapes to try
    def _mask_token(val: str) -> str:
        if not val:
            return None
        try:
            v = str(val)
        except Exception:
            return '***'
        if len(v) <= 6:
            return v[:1] + '***' + v[-1:]
        return v[:3] + '***' + v[-3:]

    def _mask_url(u: str) -> str:
        try:
            if '/token/' in u:
                parts = u.split('/token/', 1)
                token_part = parts[1]
                token_val = token_part.split('/', 1)[0] if token_part else ''
                rest = ''
                if '/' in token_part:
                    rest = '/' + token_part.split('/', 1)[1]
                return parts[0] + '/token/' + (_mask_token(token_val) or '') + rest
        except Exception:
            pass
        return u

    def _record_attempt(u: str, h: dict, p: dict, status=None, body=None):
        if os.getenv('DEBUG_ZAPI') != '1':
            return
        try:
            masked_headers = {}
            for k, v in (h or {}).items():
                if k.lower() in ('authorization', 'client-token'):
                    masked_headers[k] = _mask_token(v)
                else:
                    masked_headers[k] = v
            entry = {
                'url': _mask_url(u),
                'headers': masked_headers,
                'payload': p,
                'status': status,
                'body': body,
            }
            _LAST_DEBUG['ts'] = int(time.time())
            attempts = _LAST_DEBUG.setdefault('attempts', [])
            attempts.append(entry)
            # keep only last 5
            if len(attempts) > 5:
                del attempts[:-5]
        except Exception:
            pass

    # Normalize phone to digits only (Z-API expects international number without '+')
    clean_phone = re.sub(r"\D", "", phone)
    if os.getenv('DEBUG_ZAPI') == '1' and clean_phone != phone:
        try:
            log.debug("normalized phone: '%s' -> '%s'", phone, clean_phone)
        except Exception:
            pass

    # candidate payload forms
    payloads = [
        {"phone": clean_phone, "message": message},
        {"to": clean_phone, "text": message},
    ]

    # candidate endpoint variants (prefer existing computed url, then try send-message)
    urls = [local_zapi_url]
    if '/send-text' in local_zapi_url:
        urls.append(local_zapi_url.replace('/send-text', '/send-message'))
    elif '/send-message' in local_zapi_url:
        urls.append(local_zapi_url.replace('/send-message', '/send-text'))
    else:
        urls.append(local_zapi_url.rstrip('/') + '/send-message')

    # header variants: prefer Client-Token when available, then Authorization bearer
    header_variants = []
    base = {"Content-Type": "application/json"}
    if local_client_token:
        h = base.copy()
        h["Client-Token"] = local_client_token
        header_variants.append(h)
    if local_zapi_token:
        h2 = base.copy()
        h2["Authorization"] = f"Bearer {local_zapi_token}"
        header_variants.append(h2)

    last_err = None
    last_resp = None

    # Try combinations in deterministic order
    for u in urls:
        for h in header_variants:
            for p in payloads:
                # Debug masked logging
                if os.getenv('DEBUG_ZAPI') == '1':
                    try:
                        masked_url = _mask_url(u)
                        masked_headers = {}
                        for k, v in h.items():
                            if k.lower() in ('authorization', 'client-token'):
                                masked_headers[k] = _mask_token(v)
                            else:
                                masked_headers[k] = v
                        log.debug("Z-API request -> attempt url=%s headers=%s payload=%s", masked_url, masked_headers, p)
                        _record_attempt(u, h, p)
                    except Exception:
                        log.debug("Z-API request -> (unable to format debug info)")

                try:
                    resp = requests.post(u, json=p, headers=h, timeout=15)
                except Exception as e:
                    last_err = e
                    log.debug("Z-API request exception for url=%s: %s", u, e)
                    _record_attempt(u, h, p, status=None, body=str(e))
                    continue

                last_resp = resp
                # debug response
                if os.getenv('DEBUG_ZAPI') == '1':
                    try:
                        resp_body = resp.json()
                    except Exception:
                        resp_body = getattr(resp, 'text', '')
                    try:
                        log.debug("Z-API response -> status=%s body=%s", getattr(resp, 'status_code', None), resp_body)
                    except Exception:
                        log.debug("Z-API response -> (unable to format response)")
                    _record_attempt(u, h, p, status=getattr(resp, 'status_code', None), body=resp_body)

                # If 2xx -> return
                if 200 <= getattr(resp, 'status_code', 0) < 300:
                    try:
                        result = resp.json()
                    except Exception:
                        result = {"status": "ok", "raw": getattr(resp, 'text', '')}
                    # persist last outbound for cross-worker dedupe
                    if set_last_outbound and isinstance(clean_phone, str):
                        try:
                            set_last_outbound(clean_phone, message)
                        except Exception:
                            pass
                    return result

                # If provider clearly says instance not found, raise early (token/instance mismatch)
                try:
                    body = None
                    try:
                        body = resp.json()
                    except Exception:
                        body = getattr(resp, 'text', '')
                    if (isinstance(body, dict) and body.get('error') == 'Instance not found') or (
                        isinstance(body, str) and 'Instance not found' in body
                    ):
                        raise RuntimeError(
                            "Z-API instance not found (404). Check your ZAPI_URL and ZAP_TOKEN for typos or expired token; "
                            "also verify CLIENT_TOKEN if your instance requires it. Response body: " + str(body)
                        )
                except RuntimeError:
                    raise
                except Exception:
                    # continue trying other permutations
                    pass

                # record last error context
                last_err = RuntimeError(f"Z-API send failed status={getattr(resp,'status_code','N/A')} body={getattr(resp,'text','')} url={u}")

    # exhausted attempts
    if isinstance(last_err, Exception):
        raise last_err
    raise RuntimeError("Z-API send failed: unknown error")
