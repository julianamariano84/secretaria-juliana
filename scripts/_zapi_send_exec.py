import requests, json
url = 'https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'
headers = {
    'Authorization': 'Bearer 6ED2B6C9FBB305ACA45EF6ED',
    'Content-Type': 'application/json',
    'Client-Token': '3E68FAC9BEFB716A85B5B24F68547F08'
}
payload = {"phone": "5522988045181", "message": "Teste via assistente - execução autorizada"}
print('Sending to', url)
try:
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    print('STATUS', r.status_code)
    try:
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        print('BODY:', r.text)
except Exception as e:
    print('REQUEST ERROR:', repr(e))
