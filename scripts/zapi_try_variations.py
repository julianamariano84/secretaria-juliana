#!/usr/bin/env python3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()
url = 'https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'
# prefer env token, fallback to literal
token = os.getenv('ZAP_TOKEN') or os.getenv('ZAPI_TOKEN') or '6ED2B6C9FBB305ACA45EF6ED'
phone = '5511999999999'

attempts = []

# 1) different header names
header_names = ['Client-Token','client-token','X-Client-Token','Client-Token-Id','X-Client-Token-Id','client_token']
for hn in header_names:
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', hn: token}
    payload = {"to": phone, "message": "teste via var header"}
    attempts.append((f'header:{hn}', headers, payload))

# 2) token as JSON fields
json_fields = ['clientToken','client_token','client-token','clienttoken','token']
for jf in json_fields:
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {"to": phone, jf: token, "message": "teste via json field"}
    attempts.append((f'json:{jf}', headers, payload))

# 3) try payload as text body vs message
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
attempts.append(('payload:text-body', headers, {"to": phone, "type": "text", "text": {"body": "teste text body"}}))
attempts.append(('payload:message', headers, {"to": phone, "message": "teste message field"}))

results = []
for name, headers, payload in attempts:
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        results.append((name, resp.status_code, body))
    except Exception as e:
        results.append((name, 'ERROR', str(e)))

# print summary
for r in results:
    print('---')
    print('attempt:', r[0])
    print('status:', r[1])
    print('body:', json.dumps(r[2], ensure_ascii=False) if not isinstance(r[2], str) else r[2])
