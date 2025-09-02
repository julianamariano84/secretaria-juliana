from dotenv import load_dotenv
import os
import json
import traceback
import requests

load_dotenv()

def _mask(val: str) -> str:
    if not val:
        return val
    v = str(val)
    if len(v) <= 6:
        return v[:1] + '***' + v[-1:]
    return v[:3] + '***' + v[-3:]

ZAPI_URL = os.getenv('ZAPI_URL')
ZAP_TOKEN = os.getenv('ZAP_TOKEN') or os.getenv('ZAPI_TOKEN')
CLIENT_TOKEN = os.getenv('CLIENT_TOKEN') or os.getenv('CLIENTTOKEN') or os.getenv('CLIENT_TOKEN_ID')
PHONE = os.getenv('TEST_PHONE') or '5511999999999'
MSG = os.getenv('TEST_MESSAGE') or 'teste execucao final'

if not ZAPI_URL:
    print('ERROR: Set ZAPI_URL in the environment (no defaults).')
    raise SystemExit(2)

if '<INSTANCE_ID>' in ZAPI_URL or '<TOKEN>' in ZAPI_URL:
    print('ERROR: ZAPI_URL contains placeholders. Replace with real values from your Z-API painel.')
    raise SystemExit(2)

# Choose payload shape; default to phone/message
payload_shape = (os.getenv('ZAPI_PAYLOAD_SHAPE') or 'phone_message').lower()
if payload_shape in ('phone_message', 'phone-message', 'phone'):
    payload = { 'phone': PHONE, 'message': MSG }
elif payload_shape in ('to_message', 'to-message'):
    payload = { 'to': PHONE, 'message': MSG }
elif payload_shape in ('to_text', 'to-text', 'text'):
    payload = { 'to': PHONE, 'text': MSG }
else:
    print(f"WARN: Unknown ZAPI_PAYLOAD_SHAPE='{payload_shape}', using phone/message")
    payload = { 'phone': PHONE, 'message': MSG }

headers = { 'Content-Type': 'application/json' }
if CLIENT_TOKEN:
    headers['Client-Token'] = CLIENT_TOKEN
if ZAP_TOKEN:
    headers['Authorization'] = f'Bearer {ZAP_TOKEN}'

# Mask URL token-in-path when printing
masked_url = ZAPI_URL
if '/token/' in masked_url:
    try:
        pfx, rest = masked_url.split('/token/', 1)
        token_val, tail = (rest.split('/', 1) + [''])[:2]
        masked_url = pfx + '/token/' + (_mask(token_val) or '') + ('/' + tail if tail else '')
    except Exception:
        pass

masked_headers = {}
for k, v in headers.items():
    if k.lower() in ('authorization', 'client-token'):
        masked_headers[k] = _mask(v)
    else:
        masked_headers[k] = v

print('REQUEST URL:', masked_url)
print('REQUEST HEADERS:', json.dumps(masked_headers, ensure_ascii=False))
print('REQUEST PAYLOAD:', json.dumps(payload, ensure_ascii=False))

try:
    resp = requests.post(ZAPI_URL, json=payload, headers=headers, timeout=20)
    print('\nRESPONSE STATUS:', resp.status_code)
    try:
        j = resp.json()
        print('RESPONSE JSON:', json.dumps(j, ensure_ascii=False))
    except Exception:
        print('RESPONSE TEXT:', resp.text)
except Exception as e:
    print('REQUEST ERROR:', e)
    traceback.print_exc()
