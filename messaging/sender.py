"""Envio de mensagens via Z-API (com fallback para stub em dev).

Configurações esperadas no ambiente (.env):

Se as variáveis não estiverem presentes, o módulo cai em um stub local para desenvolvimento.
"""
"""Envio de mensagens via Z-API com fallback stub.

Esperado no .env:
- ZAPI_URL (ex: https://api.z-api.io/instances/<id>/send-message)
- ZAPI_TOKEN
"""
import os
import json
import logging

log = logging.getLogger(__name__)

# If DEBUG_ZAPI=1 is set, enable debug logging for this module
if os.getenv('DEBUG_ZAPI') == '1':
    # ensure a handler exists so debug output shows when this module is used directly
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter('%(levelname)s:%(name)s: %(message)s'))
        log.addHandler(h)
    log.setLevel(logging.DEBUG)

try:
    import requests
except Exception:
    requests = None

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

    # If no Z-API config, fallback to stub
    if not local_zapi_url and not local_zapi_token:
        return _stub_send(phone, message)

    if requests is None:
        raise RuntimeError("Biblioteca 'requests' não está disponível. Instale com pip install requests")

    if not local_zapi_url or not local_zapi_token:
        raise RuntimeError("Z-API parcialmente configurada: defina ZAPI_URL e ZAP_TOKEN (ou ZAPI_TOKEN) no .env")

    # Many Z-API instances expect a simple payload with 'message'
    # Try several payload formats because different Z-API instances accept
    # different shapes (observed: "phone", "to", "+5511...", "5511...@c.us").
    headers = {"Authorization": f"Bearer {local_zapi_token}", "Content-Type": "application/json"}
    if local_client_token:
        headers["Client-Token"] = local_client_token

    # Prefer /send-message endpoint when possible (some instances accept this and not /send-text)
    # Allow override via env ZAPI_PREFERRED_ENDPOINT: 'send-message' or 'send-text'
    # Normalize configured URL: force canonical /send-text and strip anything after it
    preferred = os.getenv('ZAPI_PREFERRED_ENDPOINT')
    if local_zapi_url:
        # If the configured URL contains '/send-text' anywhere, cut everything after it
        if '/send-text' in local_zapi_url:
            idx = local_zapi_url.find('/send-text')
            local_zapi_url = local_zapi_url[: idx + len('/send-text')]
        elif '/send-message' in local_zapi_url and preferred == 'send-text':
            # if user explicitly prefers send-text, convert send-message -> send-text
            idx = local_zapi_url.find('/send-message')
            local_zapi_url = local_zapi_url[: idx] + '/send-text'
        else:
            # ensure it ends with /send-text
            local_zapi_url = local_zapi_url.rstrip('/') + '/send-text'

    # Fast mode: if enabled, only try the proven fast payload and fail fast
    ZAPI_FAST = os.getenv('ZAPI_FAST') == '1'

    payload_variants = [
        {"phone": phone, "message": message},
        {"to": phone, "message": message},
        {"to": f"+{phone}", "message": message},
        {"to": f"{phone}@c.us", "message": message},
        {"to": phone, "type": "text", "text": {"body": message}},
    ]
    errors = []

    # Fast path: try the proven variant first (phone + message).
    first_payload = {"phone": phone, "message": message}
    debug = os.getenv('DEBUG_ZAPI') == '1'
    try:
        if debug:
            log.debug('DEBUG_ZAPI: URL=%s', str(local_zapi_url))
            log.debug('DEBUG_ZAPI: HEADERS=%s', json.dumps(headers, ensure_ascii=False))
            log.debug('DEBUG_ZAPI: PAYLOAD=%s', json.dumps(first_payload, ensure_ascii=False))

        # Always post to the canonical local_zapi_url (which was normalized above).
        # If the configured URL includes a token path segment, avoid sending duplicate
        # auth headers by using a lean headers set.
        token_in_path = '/token/' in str(local_zapi_url)
        headers_fast = {'Content-Type': 'application/json'} if token_in_path else headers
        resp = requests.post(local_zapi_url, json=first_payload, headers=headers_fast, timeout=15)

        if resp.ok:
            # Some Z-API instances return HTTP 200 but include an error object in JSON
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = None

            if resp_json and isinstance(resp_json, dict) and resp_json.get('error'):
                # treat as failure and continue to next variant
                # record clear diagnostics (status, attempted url, and body text)
                try:
                    status_code = getattr(resp, 'status_code', 'N/A')
                    body_text = json.dumps(resp_json, ensure_ascii=False)
                except Exception:
                    status_code = getattr(resp, 'status_code', 'N/A')
                    body_text = getattr(resp, 'text', '')

                attempted_url = None
                try:
                    attempted_url = resp.request.url if hasattr(resp, 'request') and getattr(resp.request, 'url', None) else None
                except Exception:
                    attempted_url = None

                errors.append(f"payload[fast] status={status_code} url={attempted_url} body={body_text}")
                if debug:
                    log.debug('DEBUG_ZAPI: RESPONSE_STATUS=%s', str(status_code))
                    log.debug('DEBUG_ZAPI: RESPONSE_TEXT=%s', body_text)
                # continue to next payload variant instead of returning
            else:
                try:
                    if debug:
                        log.debug('DEBUG_ZAPI: RESPONSE_STATUS=%s', str(getattr(resp, 'status_code', 'N/A')))
                        log.debug('DEBUG_ZAPI: RESPONSE_JSON=%s', json.dumps(resp_json if resp_json is not None else {}, ensure_ascii=False))
                    return resp_json if resp_json is not None else {"status": "ok", "raw": getattr(resp, 'text', '')}
                except Exception:
                    if debug:
                        log.debug('DEBUG_ZAPI: RESPONSE_TEXT=%s', getattr(resp, 'text', ''))
                    return {"status": "ok", "raw": getattr(resp, 'text', '')}

        # record non-ok response for diagnostics and proceed to fallback
        errors.append(f"payload[fast] status={getattr(resp, 'status_code', 'N/A')} body={getattr(resp, 'text', '')}")
        if debug:
            log.debug('DEBUG_ZAPI: RESPONSE_STATUS=%s', str(getattr(resp, 'status_code', 'N/A')))
            log.debug('DEBUG_ZAPI: RESPONSE_TEXT=%s', getattr(resp, 'text', ''))

    except Exception as e:
        errors.append(f"payload[fast] request error: {e}")
        if debug:
            log.exception('payload[fast] request error')

    # If fast mode is enabled, fail fast with the diagnostics we collected
    if ZAPI_FAST:
        raise RuntimeError("Z-API send failed (fast mode); attempts:\n" + "\n".join(errors))

    # Fallback: try remaining payload variants in order, always to the canonical URL
    for idx, payload in enumerate(payload_variants[1:], 2):
        log.debug("Z-API try %d payload: %s", idx, payload)
        debug = os.getenv('DEBUG_ZAPI') == '1'
        if debug:
            log.debug('DEBUG_ZAPI: URL=%s', str(local_zapi_url))
            log.debug('DEBUG_ZAPI: HEADERS=%s', json.dumps(headers, ensure_ascii=False))
            log.debug('DEBUG_ZAPI: PAYLOAD=%s', json.dumps(payload, ensure_ascii=False))

        try:
            resp = requests.post(local_zapi_url, json=payload, headers=headers, timeout=15)
        except Exception as e:
            errors.append(f"payload[{idx}] request error: {e}")
            if debug:
                log.exception('payload[%s] request error', idx)
            continue

        if resp.ok:
            try:
                if debug:
                    log.debug('DEBUG_ZAPI: RESPONSE_STATUS=%s', str(getattr(resp, 'status_code', 'N/A')))
                    log.debug('DEBUG_ZAPI: RESPONSE_JSON=%s', json.dumps(resp.json(), ensure_ascii=False))
                return resp.json()
            except Exception:
                if debug:
                    log.debug('DEBUG_ZAPI: RESPONSE_TEXT=%s', getattr(resp, 'text', ''))
                return {"status": "ok", "raw": getattr(resp, 'text', '')}

        errors.append(f"payload[{idx}] status={getattr(resp, 'status_code', 'N/A')} body={getattr(resp, 'text', '')}")
        if debug:
            log.debug('DEBUG_ZAPI: RESPONSE_STATUS=%s', str(getattr(resp, 'status_code', 'N/A')))
            log.debug('DEBUG_ZAPI: RESPONSE_TEXT=%s', getattr(resp, 'text', ''))

    # If we reached here, none of the variants succeeded
    # Note: we intentionally do NOT try alternate URLs or mutate the configured URL further.
    # The integration must post only to the canonical /send-text address the user requested.
    alt_errors = []

    # Combine diagnostics and raise
    all_err = errors + alt_errors
    raise RuntimeError("Z-API send failed; attempts:\n" + "\n".join(all_err))
