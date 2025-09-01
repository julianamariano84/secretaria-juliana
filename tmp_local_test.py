import os
import logging
import json

os.environ['DEBUG_ZAPI'] = '1'
logging.basicConfig(level=logging.DEBUG)

from app import create_app
app = create_app()
client = app.test_client()

payload = {'message': {'from': '5511999999999', 'text': 'Bom dia'}}
resp = client.post('/webhook/inbound', json=payload)
print('STATUS:', resp.status_code)
print('BODY:', resp.get_data(as_text=True))

# show registrations file
store = os.path.join(os.path.dirname(__file__), 'data', 'registrations.json')
try:
    with open(store, 'r', encoding='utf-8') as f:
        print('\nREGISTRATIONS FILE:')
        print(f.read())
except Exception as e:
    print('Could not read registrations file:', e)
