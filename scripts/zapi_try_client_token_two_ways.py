#!/usr/bin/env python3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()
instance_id = os.getenv('ZAPI_INSTANCE') or os.getenv('ZAPI_ID') or '3E68FAC9BEFB716A85B5B24F68547F08'
instance_token = os.getenv('ZAP_TOKEN') or os.getenv('ZAPI_TOKEN') or '6ED2B6C9FBB305ACA45EF6ED'
url = f'https://api.z-api.io/instances/{instance_id}/token/{instance_token}/send-text'
phone = '5511999999999'
payload = {"to": phone, "message": "teste tentativa client-token"}

attempts = [
    ('Client-Token=instance_token', instance_token),
    ('Client-Token=instance_id', instance_id)
]

for name, client_token in attempts:
    headers = {
        'Authorization': f'Bearer {instance_token}',
        'Content-Type': 'application/json',
        'Client-Token': client_token
    }
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
