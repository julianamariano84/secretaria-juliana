from dotenv import load_dotenv
import os, json, sys

# Ensure repo root is on sys.path so sibling packages (like `messaging`) can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv()
from messaging import sender

os.environ['DEBUG_ZAPI'] = '1'
# Use env values or defaults
os.environ.setdefault('ZAPI_URL', 'https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text')
os.environ.setdefault('ZAP_TOKEN', '6ED2B6C9FBB305ACA45EF6ED')
os.environ.setdefault('CLIENT_TOKEN', 'F46fd6dff25a346d79a7c0a869e97f975S')

try:
    res = sender.send_text('5511999999999','teste exec quiet')
    print('RESULT_OK')
    print(json.dumps(res,ensure_ascii=False))
except Exception as e:
    print('EXCEPTION')
    print(str(e))
    sys.exit(1)
