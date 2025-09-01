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
        if 'Extraia dados' in content:
            return FakeResp('{"name":"João Silva","dob":"1985-03-12","cpf":"12345678909","address":"Rua das Flores 123","confirm":true}')
        else:
            return FakeResp('1. Nome completo?\n2. Data de nascimento?\n3. CPF?\n4. Endereço?\n5. Você confirma?')

class FakeClient:
    chat = FakeChat()

# monkeypatch
o._require_client = lambda: FakeClient()

out = []
out.append('=== RUN_AND_LOG_OPENAI START ===')
try:
    out.append('extract_registration_fields ->')
    out.append(json.dumps(o.extract_registration_fields('texto qualquer'), ensure_ascii=False, indent=2))
except Exception as e:
    out.append('extract error: ' + str(e))

try:
    out.append('\ngenerate_registration_questions ->')
    out.append(json.dumps(o.generate_registration_questions(), ensure_ascii=False, indent=2))
except Exception as e:
    out.append('generate error: ' + str(e))

out.append('=== END ===')
with open('tests/openai_test_output.log', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('WROTE tests/openai_test_output.log')
