#!/usr/bin/env python3
from dotenv import load_dotenv
import os, json, requests

load_dotenv()
url = 'https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'
token = os.getenv('ZAP_TOKEN') or os.getenv('ZAPI_TOKEN')
payload = {"to": "5511999999999", "type": "text", "text": {"body": "teste verbose via script"}}
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print('REQUEST URL:', url)
print('REQUEST HEADERS:', json.dumps(headers, ensure_ascii=False))
print('REQUEST PAYLOAD:', json.dumps(payload, ensure_ascii=False))

try:
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    print('\nRESPONSE STATUS:', resp.status_code)
    print('RESPONSE HEADERS:', dict(resp.headers))
    # print pretty JSON if possible, else raw text
    try:
        print('RESPONSE JSON:', json.dumps(resp.json(), ensure_ascii=False))
    except Exception:
        print('RESPONSE TEXT:', resp.text)
except Exception as e:
    print('REQUEST ERROR:', e)
