import os
import sys
import pathlib

# ensure project root is on sys.path so `services` can be imported
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from services.openai_client import (
    local_extract_registration_fields,
    generate_greeting_and_action,
)


def test_local_extractor_basic():
    txt = (
        "Olá, meu nome é João Silva, nasci em 12/03/1985, CPF 111.444.777-35, "
        "moro na Rua das Flores 123. Confirmo o cadastro."
    )
    out = local_extract_registration_fields(txt)
    assert out is not None
    assert out.get('name') and out['name'].startswith('João')
    assert out.get('dob') == '12/03/1985'
    assert out.get('cpf') == '11144477735'
    assert out.get('address') is not None and 'Rua' in out['address']
    assert out.get('confirm') is True


def test_generate_greeting_and_action_fallback_all_fields(monkeypatch):
    # Ensure OpenAI client is not used by removing API key
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)

    txt = (
        "Olá, meu nome é João Silva, nasci em 12/03/1985, CPF 111.444.777-35, "
        "moro na Rua das Flores 123. Confirmo o cadastro."
    )
    res = generate_greeting_and_action(txt, first_contact=False)
    # When all fields are present, the heuristic fallback should ask for confirmation
    assert isinstance(res, dict)
    assert res.get('action') == 'confirm'
    assert isinstance(res.get('greeting'), str) and res.get('greeting')


def test_first_contact_greeting(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('SECRETARY_NAME', 'Márcia')

    res = generate_greeting_and_action('Oi', first_contact=True)
    assert isinstance(res, dict)
    assert 'secretária' in res.get('greeting') or 'Márcia' in res.get('greeting')
    assert res.get('action') == 'ask'
