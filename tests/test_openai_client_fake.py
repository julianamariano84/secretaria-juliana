import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import services.openai_client as o

class FakeResp:
    class Message:
        def __init__(self, content):
            self.content = content
    class Choice:
        def __init__(self, content):
            self.message = FakeResp.Message(content)
    def __init__(self, content):
        self.choices = [FakeResp.Choice(content)]

class FakeChat:
    @staticmethod
    def create(*args, **kwargs):
        messages = kwargs.get('messages') or []
        content = messages[0]['content'] if messages else ''
        if 'Extraia dados' in content or 'Extraia dados' in (messages[0].get('content','') if messages else ''):
            # return a compact JSON object
            return FakeResp('{"name":"João Silva","dob":"1985-03-12","cpf":"12345678909","address":"Rua das Flores 123","confirm":true}')
        else:
            # return a list-like set of lines
            return FakeResp('1. Nome completo?\n2. Data de nascimento?\n3. CPF?\n4. Endereço?\n5. Você confirma?')

class FakeClient:
    chat = FakeChat()

# monkeypatch the _require_client to return our fake client
o._require_client = lambda: FakeClient()

print('=== FAKE TEST START ===')
print('extract_registration_fields ->')
print(json.dumps(o.extract_registration_fields('texto qualquer'), ensure_ascii=False, indent=2))
print('\ngenerate_registration_questions ->')
print(json.dumps(o.generate_registration_questions(), ensure_ascii=False, indent=2))
print('=== FAKE TEST END ===')
