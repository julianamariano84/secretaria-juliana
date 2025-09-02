import importlib, traceback

try:
    m = importlib.import_module('messaging.sender')
    print('MODULE IMPORTED')
    print('module file:', getattr(m, '__file__', 'n/a'))
    print('has send_text:', hasattr(m, 'send_text'))
    print('send_text callable:', callable(getattr(m, 'send_text', None)))
except Exception:
    print('IMPORT ERROR:')
    traceback.print_exc()
