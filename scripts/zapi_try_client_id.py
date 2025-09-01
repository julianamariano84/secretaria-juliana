#!/usr/bin/env python3
import json, requests

# Endpoint
url = 'https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'
print('SCRIPT START')
# Client token provided by user (trying as client token)
client_token = '3E68FAC9BEFB716A85B5B24F68547F08'
phone = '5511999999999'

attempts = []
# header variations
for hn in ['Client-Token','client-token','X-Client-Token','Client-Token-Id','X-Client-Token-Id','client_token','X-ClientToken']:
    headers = {'Authorization': f'Bearer {client_token}', 'Content-Type': 'application/json', hn: client_token}
    payload = {"to": phone, "message": "teste client id header"}
    attempts.append((f'header:{hn}', headers, payload))
# json field variations
for jf in ['clientToken','client_token','client-token','clienttoken','token','clientId']:
    headers = {'Authorization': f'Bearer {client_token}', 'Content-Type': 'application/json'}
    payload = {"to": phone, jf: client_token, "message": "teste client id json"}
    attempts.append((f'json:{jf}', headers, payload))

results = []
for idx, (name, headers, payload) in enumerate(attempts, 1):
    print(f'Attempt {idx}/{len(attempts)} ->', name)
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        results.append((name, resp.status_code, body))
        print('  status:', resp.status_code)
    except Exception as e:
        results.append((name, 'ERROR', str(e)))
        print('  error:', e)

for r in results:
    print('---')
    print('attempt:', r[0])
    print('status:', r[1])
    print('body:', json.dumps(r[2], ensure_ascii=False) if not isinstance(r[2], str) else r[2])
