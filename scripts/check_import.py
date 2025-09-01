import importlib, traceback

try:
    m = importlib.import_module('app')
    print('MODULE IMPORTED')
    print('has attribute app:', hasattr(m, 'app'))
    a = getattr(m, 'app', None)
    print('app repr:', repr(a))
except Exception:
    print('IMPORT ERROR:')
    traceback.print_exc()
