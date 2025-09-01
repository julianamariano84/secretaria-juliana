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

        resp = requests.post(local_zapi_url, json=first_payload, headers=headers, timeout=15)

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

    # Fallback: try remaining payload variants in order
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
    raise RuntimeError("Z-API send failed; attempts:\n" + "\n".join(errors))
