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
    preferred = os.getenv('ZAPI_PREFERRED_ENDPOINT')
    send_message_url = None
    if local_zapi_url:
        # If ZAPI_URL already points to a specific endpoint, keep it; otherwise try to construct
        if local_zapi_url.endswith('/send-text') or local_zapi_url.endswith('/send-message'):
            send_message_url = local_zapi_url.replace('/send-text', '/send-message')
        else:
            # assume base URL like https://api.z-api.io/instances/<id>/token/<token>
            send_message_url = local_zapi_url.rstrip('/') + '/send-message'

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

        # If preference is to try /send-message first, use that URL when available
        tried_urls = []
        if preferred == 'send-message' or preferred is None:
            if send_message_url:
                tried_urls.append(send_message_url)
                resp = requests.post(send_message_url, json=first_payload, headers=headers, timeout=15)
            else:
                resp = requests.post(local_zapi_url, json=first_payload, headers=headers, timeout=15)
        else:
            resp = requests.post(local_zapi_url, json=first_payload, headers=headers, timeout=15)

        if resp.ok:
            # Some Z-API instances return HTTP 200 but include an error object in JSON
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = None

            if resp_json and isinstance(resp_json, dict) and resp_json.get('error'):
                # treat as failure and continue to next variant
                err_msg = f"payload[{idx}] provider_error={resp_json.get('error')} message={resp_json.get('message')}"
                errors.append(err_msg)
                if debug:
                    log.debug('DEBUG_ZAPI: RESPONSE_STATUS=%s', str(getattr(resp, 'status_code', 'N/A')))
                    try:
                        log.debug('DEBUG_ZAPI: RESPONSE_JSON=%s', json.dumps(resp_json, ensure_ascii=False))
                    except Exception:
                        log.debug('DEBUG_ZAPI: RESPONSE_TEXT=%s', getattr(resp, 'text', ''))
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
    # Extra attempts: some Z-API instances expose slightly different paths or expect different payloads.
    # If the provider returned NOT_FOUND we try alternate URLs and payload shapes to be resilient.
    debug = os.getenv('DEBUG_ZAPI') == '1'
    alt_errors = []

    try:
        # build alternate URLs
        alt_urls = []
        if local_zapi_url:
            # swap send-text <-> send-message
            alt_urls.append(local_zapi_url.replace('/send-text', '/send-message'))
            alt_urls.append(local_zapi_url.replace('/send-message', '/send-text'))
            # try removing /token/<token> segment (some instances accept token via header)
            import re
            alt_no_token = re.sub(r'/token/[^/]+', '', local_zapi_url)
            alt_no_token = alt_no_token.rstrip('/')
            alt_urls.append(alt_no_token + '/send-text')
            alt_urls.append(alt_no_token + '/send-message')

        # additional payload shapes to try when NOT_FOUND occurs
        extra_payloads = [
            {"to": phone, "message": message},
            {"to": f"{phone}@c.us", "message": message},
            {"to": phone, "type": "text", "text": {"body": message}},
            {"chatId": phone, "body": message},
            {"number": phone, "message": message},
        ]

        for u in alt_urls:
            for pidx, p in enumerate(extra_payloads, 1):
                if debug:
                    log.debug('DEBUG_ZAPI: ALT TRY URL=%s PAYLOAD=%s', u, json.dumps(p, ensure_ascii=False))
                try:
                    # try without client-token header first
                    h = headers.copy()
                    if 'Client-Token' in h:
                        del h['Client-Token']
                    resp = requests.post(u, json=p, headers=h, timeout=15)
                except Exception as e:
                    alt_errors.append(f"alt request error {u} payload#{pidx}: {e}")
                    if debug:
                        log.exception('alt request error')
                    continue

                try:
                    body_text = getattr(resp, 'text', '')
                    status = getattr(resp, 'status_code', 'N/A')
                    if debug:
                        log.debug('DEBUG_ZAPI: ALT RESPONSE_STATUS=%s', str(status))
                        log.debug('DEBUG_ZAPI: ALT RESPONSE_TEXT=%s', body_text)
                    # if provider returns JSON accepted result, return it
                    if resp.ok:
                        # check for JSON error payload even when HTTP 200
                        try:
                            alt_json = resp.json()
                        except Exception:
                            alt_json = None

                        if alt_json and isinstance(alt_json, dict) and alt_json.get('error'):
                            alt_errors.append(f"alt[{u}] provider_error={alt_json.get('error')} message={alt_json.get('message')}")
                            if debug:
                                log.debug('DEBUG_ZAPI: ALT RESPONSE_JSON=%s', json.dumps(alt_json, ensure_ascii=False))
                            # continue to next alt
                        else:
                            try:
                                return alt_json if alt_json is not None else {"status": "ok", "raw": body_text}
                            except Exception:
                                return {"status": "ok", "raw": body_text}
                    # otherwise record and continue
                    alt_errors.append(f"alt[{u}] status={status} body={body_text}")
                except Exception:
                    alt_errors.append(f"alt[{u}] unkfail")

    except Exception:
        if debug:
            log.exception('extra alt attempts failed')

    # Combine diagnostics and raise
    all_err = errors + alt_errors
    raise RuntimeError("Z-API send failed; attempts:\n" + "\n".join(all_err))
