import sys, pathlib, json
import threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import services.openai_client as o

def run_with_timeout(fn, args=(), timeout=8):
    result = {'v': None, 'exc': None}
    def target():
        try:
            result['v'] = fn(*args)
        except Exception as e:
            result['exc'] = e
    t = threading.Thread(target=target)
    t.start()
    t.join(timeout)
    if t.is_alive():
        print('TIMEOUT')
        return None
    if result['exc']:
        print('EXC', result['exc'])
        return None
    return result['v']

print('CALLING extract_registration_fields (with timeout)')
r = run_with_timeout(o.extract_registration_fields, ('teste',), 8)
print('GOT:', type(r), repr(r))
print('\nCALLING generate_registration_questions (with timeout)')
r2 = run_with_timeout(o.generate_registration_questions, (), 8)
print('GOT2:', type(r2), repr(r2))
