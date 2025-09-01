import sys
import pathlib
# ensure project root is on sys.path so `services` can be imported
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import services.openai_client as o
import json

sample_text = (
    "Olá, meu nome é João Silva, nasci em 12/03/1985, CPF 123.456.789-09, "
    "moro na Rua das Flores 123. Confirmo o cadastro."
)

def safe_call(fn, *args):
    try:
        r = fn(*args)
        print('RESULT', fn.__name__, json.dumps(r, ensure_ascii=False))
    except Exception as e:
        print('EXCEPTION', fn.__name__, str(e))

if __name__ == '__main__':
    print('\n--- RUNNING test_openai_client.py ---')
    safe_call(o.extract_registration_fields, sample_text)
    safe_call(o.generate_registration_questions)
    print('\n--- DONE ---')
