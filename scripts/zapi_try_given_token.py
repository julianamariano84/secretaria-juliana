#!/usr/bin/env python3
import json, requests, os
from dotenv import load_dotenv

load_dotenv()
instance_id = os.getenv('ZAPI_INSTANCE') or '3E68FAC9BEFB716A85B5B24F68547F08'
instance_token = os.getenv('ZAP_TOKEN') or '6ED2B6C9FBB305ACA45EF6ED'
# URL using instance/token path
url = f'https://api.z-api.io/instances/{instance_id}/token/{instance_token}/send-text'
phone = '5511999999999'
# token to test (from user)
token_to_test = '6ED2B6C9FBB305ACA45EF6ED'

# Attempt 1: header Client-Token = token_to_test
headers1 = {'Authorization': f'Bearer {instance_token}', 'Content-Type': 'application/json', 'Client-Token': token_to_test}
payload1 = {"to": phone, "message": "teste token do usuario - header"}

# Attempt 2: json field clientToken = token_to_test
headers2 = {'Authorization': f'Bearer {instance_token}', 'Content-Type': 'application/json'}
payload2 = {"to": phone, "clientToken": token_to_test, "message": "teste token do usuario - json"}

attempts = [
    ('header:Client-Token', headers1, payload1),
    ('json:clientToken', headers2, payload2),
]

for name, headers, payload in attempts:
    print('\n=== Attempt:', name, '===')
    print('REQUEST URL:', url)
    print('REQUEST HEADERS:', json.dumps(headers, ensure_ascii=False))
    print('REQUEST PAYLOAD:', json.dumps(payload, ensure_ascii=False))
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        print('RESPONSE STATUS:', resp.status_code)
        try:
            print('RESPONSE JSON:', json.dumps(resp.json(), ensure_ascii=False))
        except Exception:
            print('RESPONSE TEXT:', resp.text)
    except Exception as e:
        print('REQUEST ERROR:', e)
