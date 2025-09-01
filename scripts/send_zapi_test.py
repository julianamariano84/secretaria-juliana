"""Script de teste para envio real via Z-API.

Uso:
  - Configure no ambiente: ZAPI_URL, ZAP_TOKEN (ou ZAPI_TOKEN). Opcional: CLIENT_TOKEN, DEBUG_ZAPI=1
  - Rode: python scripts/send_zapi_test.py --phone 5511999999999 --message "Mensagem de teste"

O script importará e usará `messaging.sender.send_text` para enviar e imprimir a resposta.
"""
import argparse
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from messaging import sender


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phone', required=True, help='Telefone em formato internacional, ex: 5511999999999')
    p.add_argument('--message', required=False, default='Mensagem de teste da integração Z-API', help='Texto a enviar')
    args = p.parse_args()

    print('Ambiente:')
    print('  ZAPI_URL=', os.getenv('ZAPI_URL'))
    print('  ZAP_TOKEN=', 'SET' if os.getenv('ZAP_TOKEN') or os.getenv('ZAPI_TOKEN') else 'MISSING')
    print('  CLIENT_TOKEN=', os.getenv('CLIENT_TOKEN'))
    print('  DEBUG_ZAPI=', os.getenv('DEBUG_ZAPI'))

    try:
        resp = sender.send_text(args.phone, args.message)
        print('\nResposta do Z-API (parsed):')
        try:
            print(json.dumps(resp, ensure_ascii=False, indent=2))
        except Exception:
            print(resp)
        return 0
    except Exception as e:
        print('\nErro ao enviar:', e)
        return 2


if __name__ == '__main__':
    sys.exit(main())
