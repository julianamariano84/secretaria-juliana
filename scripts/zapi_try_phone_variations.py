#!/usr/bin/env python3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()
instance_id = os.getenv('ZAPI_INSTANCE') or '3E68FAC9BEFB716A85B5B24F68547F08'
instance_token = os.getenv('ZAP_TOKEN') or '6ED2B6C9FBB305ACA45EF6ED'
# Using the client token user provided earlier
client_token = 'F46fd6dff25a346d79a7c0a869e97f975S'
url = f'https://api.z-api.io/instances/{instance_id}/token/{instance_token}/send-text'

variants = [
    ({'to':'5511999999999'}, 'to: 5511999999999'),
    ({'phone':'5511999999999'}, 'phone: 5511999999999'),
    ({'number':'5511999999999'}, 'number: 5511999999999'),
    ({'to':'+5511999999999'}, 'to with +: +5511999999999'),
    ({'to':'5511999999999@c.us'}, 'to with @c.us: 5511999999999@c.us'),
    ({'to':{'phone':'5511999999999'}}, 'to as object: {"phone": "5511999999999"}'),
]

for payload_core, label in variants:
    payload = dict(payload_core)
    payload['message'] = f'teste phone variant - {label}'
    headers = {'Authorization': f'Bearer {instance_token}', 'Content-Type': 'application/json', 'Client-Token': client_token}

    print('\n=== Attempt:', label, '===')
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
