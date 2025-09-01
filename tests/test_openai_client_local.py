import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from services.openai_client import local_extract_registration_fields

examples = [
        (
        "Olá, meu nome é João Silva, nasci em 12/03/1985, CPF 111.444.777-35, moro na Rua das Flores 123. Confirmo o cadastro.",
        {
            'name': 'João Silva',
            'dob': '12/03/1985',
            'cpf': '11144477735',
                'address': 'Rua Das Flores, 123',
            'confirm': True,
        }
    ),
        (
        "Nome: Maria Oliveira. Data de nascimento: 1990-01-01. CPF: 11144477735. Endereço: Avenida Central 45.",
        {
            'name': 'Maria Oliveira',
            'dob': '01/01/1990',
            'cpf': '11144477735',
                'address': 'Avenida Central, 45',
            'confirm': None,
        }
    ),
]

def run_examples():
    for txt, expected in examples:
        out = local_extract_registration_fields(txt)
        print('INPUT:', txt)
        print('OUTPUT:', json.dumps(out, ensure_ascii=False))
        print('EXPECTED (approx):', expected)
        print('---')

if __name__ == '__main__':
    run_examples()
