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

    # Single payload: phone + message
    payload = {"phone": phone, "message": message}

    # Build headers: prefer Client-Token header when present (proven working variant)
    headers_out = {"Content-Type": "application/json"}
    # If CLIENT_TOKEN is configured, always send it as Client-Token header (proved working).
    if local_client_token:
        headers_out["Client-Token"] = local_client_token
    else:
        # fallback to Authorization header only when client token isn't present
        headers_out["Authorization"] = f"Bearer {local_zapi_token}"

    try:
        resp = requests.post(local_zapi_url, json=payload, headers=headers_out, timeout=15)
    except Exception as e:
        raise RuntimeError(f"Z-API request failed: {e}")

    # Interpret response: 2xx -> try to return parsed JSON, else raise with body
    if 200 <= getattr(resp, 'status_code', 0) < 300:
        try:
            return resp.json()
        except Exception:
            return {"status": "ok", "raw": getattr(resp, 'text', '')}

    # Non-2xx -> try to surface useful error info
    body = None
    try:
        body = resp.json()
    except Exception:
        body = getattr(resp, 'text', '')

    # Helpful, specific error for a common misconfiguration
    try:
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
        # fall through to generic error below on unexpected shape
        pass

    raise RuntimeError(f"Z-API send failed status={getattr(resp,'status_code','N/A')} body={body}")
