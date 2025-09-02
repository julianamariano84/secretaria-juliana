from dotenv import load_dotenv
import os, json, requests, traceback

load_dotenv()

ZAPI_URL = os.getenv('ZAPI_URL') or 'https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'
instance_token = os.getenv('ZAP_TOKEN') or '6ED2B6C9FBB305ACA45EF6ED'
client_token = os.getenv('CLIENT_TOKEN') or 'F46fd6dff25a346d79a7c0a869e97f975S'

headers = {
    'Authorization': f'Bearer {instance_token}',
    'Content-Type': 'application/json',
    'Client-Token': client_token,
}

payload = {
    'to': '5511999999999',
    'message': 'teste execucao final'
}

print('REQUEST URL:', ZAPI_URL)
print('REQUEST HEADERS:', json.dumps(headers, ensure_ascii=False))
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
