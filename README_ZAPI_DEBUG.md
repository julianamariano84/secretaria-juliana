Instruções rápidas para debugar Z-API com `messaging.sender` (PowerShell)

Objetivo
- Executar a função `messaging.sender.send_text` no ambiente do repositório com `DEBUG_ZAPI=1` para que o módulo imprima o URL, headers, payload e a resposta completa.

Como usar (PowerShell)
1) Abra PowerShell na pasta do repositório (onde `app.py` está):

```powershell
Set-Location 'C:\Users\mario\OneDrive\Documentos\secretaria_juliana'
```

2) Rode este comando (substitua os valores se quiser usar outros tokens):

```powershell
$env:DEBUG_ZAPI='1'; $env:ZAPI_URL='https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'; $env:ZAP_TOKEN='6ED2B6C9FBB305ACA45EF6ED'; $env:CLIENT_TOKEN='F3c15e38a9d7443309983ea194d18900cS'; & 'C:\Users\mario\AppData\Local\Programs\Python\Python313\python.exe' -c "from messaging import sender; print(sender.send_text('5511999999999','teste exec debug'))" 2>&1 | Tee-Object zapi_debug_output.txt
```

- Explicação rápida:
  - `DEBUG_ZAPI=1` ativa os prints detalhados que escrevi em `messaging/sender.py`.
  - O comando final imprime na tela e salva tudo em `zapi_debug_output.txt` na pasta do projeto.

3) Após a execução, abra `zapi_debug_output.txt` e copie o conteúdo aqui (ou anexe). Eu vou analisar e ajustar `messaging/sender.py` conforme necessário.

Se preferir um POST direto (sem passar pelo código do projeto), use este comando único (vai mostrar URL/headers/payload e resposta):

```powershell
$env:ZAP_TOKEN='6ED2B6C9FBB305ACA45EF6ED'; $env:CLIENT_TOKEN='F3c15e38a9d7443309983ea194d18900cS'; & 'C:\Users\mario\AppData\Local\Programs\Python\Python313\python.exe' - <<'PY'
import os,json,requests,sys
ZAPI_URL='https://api.z-api.io/instances/3E68FAC9BEFB716A85B5B24F68547F08/token/6ED2B6C9FBB305ACA45EF6ED/send-text'
headers={'Authorization':f"Bearer {os.getenv('ZAP_TOKEN')}",'Content-Type':'application/json','Client-Token':os.getenv('CLIENT_TOKEN')}
payload={'to':'5511999999999','message':'teste execucao final'}
print('REQUEST URL:',ZAPI_URL,file=sys.stderr)
print('REQUEST HEADERS:',json.dumps(headers,ensure_ascii=False),file=sys.stderr)
print('REQUEST PAYLOAD:',json.dumps(payload,ensure_ascii=False),file=sys.stderr)
r=requests.post(ZAPI_URL,json=payload,headers=headers,timeout=20)
print('RESPONSE STATUS:',r.status_code,file=sys.stderr)
try:
    print('RESPONSE JSON:',json.dumps(r.json(),ensure_ascii=False),file=sys.stderr)
except Exception:
    print('RESPONSE TEXT:',r.text,file=sys.stderr)
PY
```

Privacidade e segurança
- Não cole tokens em público. Se for compartilhar a saída aqui, você pode substituir manualmente os tokens por `***` antes de colar.

Se quiser, eu adapto o comando para outro número de telefone ou para salvar apenas o JSON de resposta em um arquivo separado.
