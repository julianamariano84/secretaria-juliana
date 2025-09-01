import os, json, sys
# ensure workspace root is on sys.path
root = os.path.dirname(os.path.dirname(__file__))
if root not in sys.path:
    sys.path.insert(0, root)

os.environ['ZAPI_URL']='https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'
os.environ['ZAP_TOKEN']='6ED2B6C9FBB305ACA45EF6ED'
os.environ['DEBUG_ZAPI']='1'
from messaging.sender import send_text

try:
    r = send_text('+5522988045181', 'Texto do teste')
    print(json.dumps({'ok': True, 'result': r}, ensure_ascii=False))
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)}))
