#!/usr/bin/env python3
"""End-to-end dry-run script

Usage: run this from the project root. It will try to contact the local Flask
app at http://127.0.0.1:5000. If the app is not running it will start
`python app.py` in a subprocess and wait for health to be available.

The script simulates an incoming contact (webhook), posts answers to
complete registration, and calls the schedule endpoint. It uses dry-run
behavior (does not require real Z-API or Terapee credentials) — set
environment variables DEBUG_ZAPI=1 and DEBUG_WEBHOOK=1 before running to
ensure no real messages are sent and admin endpoints are enabled.
"""

import os
import sys
import time
import subprocess
import requests
import json
import random


BASE = os.getenv('E2E_BASE') or 'http://127.0.0.1:5000'
HEALTH = BASE + '/health'
INBOUND = BASE + '/webhook/inbound'
ADMIN_REGS = BASE + '/admin/registrations'
SCHEDULE = BASE + '/api/secretaria/schedule'


def wait_for_health(timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(HEALTH, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_app_if_needed():
    try:
        if wait_for_health(1):
            print('[e2e] app already running')
            return None
    except Exception:
        pass

    print('[e2e] starting app (python app.py)')
    env = os.environ.copy()
    # ensure DEBUG flags for dry-run
    env.setdefault('DEBUG_ZAPI', '1')
    env.setdefault('DEBUG_WEBHOOK', '1')
    p = subprocess.Popen([sys.executable, 'app.py'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if not wait_for_health(30):
        print('[e2e] app did not become healthy in time; check app.py logs')
        return p
    print('[e2e] app is healthy')
    return p


def simulate_inbound(phone: str, text: str):
    payload = {'from': phone, 'text': text}
    print(f'[e2e] POST inbound -> {payload}')
    r = requests.post(INBOUND, json=payload, timeout=10)
    try:
        print('[e2e] inbound response:', r.status_code, r.json())
    except Exception:
        print('[e2e] inbound raw response:', r.status_code, r.text)
    return r


def get_pending_regs():
    try:
        r = requests.get(ADMIN_REGS, timeout=5)
        return r.json()
    except Exception as e:
        print('[e2e] admin regs request failed:', e)
        return None


def complete_registration(phone: str):
    # send a sequence of replies that the local extractor understands
    replies = [
        'Meu nome é João Silva',
        '12/03/1985',
        '111.444.777-35',
        'Rua das Flores 123',
        'SIM'
    ]
    for r in replies:
        simulate_inbound(phone, r)
        time.sleep(0.6)


def request_schedule(name: str, phone: str, date: str, time_str: str):
    body = {'name': name, 'phone': phone, 'date': date, 'time': time_str}
    print('[e2e] POST schedule ->', body)
    r = requests.post(SCHEDULE, json=body, timeout=10)
    try:
        print('[e2e] schedule response:', r.status_code, r.json())
    except Exception:
        print('[e2e] schedule raw response:', r.status_code, r.text)
    return r


def main():
    # ensure we run in project root where app.py exists
    p = start_app_if_needed()

    phone = os.getenv('E2E_PHONE') or f'55119{random.randint(90000000,99999999)}'
    initial_text = (
        'Olá, meu nome é João Silva, nasci em 12/03/1985, CPF 111.444.777-35, '
        'moro na Rua das Flores 123. Confirmo o cadastro.'
    )

    try:
        simulate_inbound(phone, initial_text)
        time.sleep(1)

        regs = get_pending_regs()
        print('[e2e] pending registrations (snapshot):')
        print(json.dumps(regs, ensure_ascii=False, indent=2))

        print('[e2e] completing registration by sending replies...')
        complete_registration(phone)
        time.sleep(1)

        regs2 = get_pending_regs()
        print('[e2e] pending registrations after replies:')
        print(json.dumps(regs2, ensure_ascii=False, indent=2))

        print('[e2e] requesting schedule (stub)')
        today = time.localtime()
        date = f"{today.tm_mday:02d}/{today.tm_mon:02d}/{today.tm_year}"
        request_schedule('João Silva', phone, date, '10:00')

        print('[e2e] check data/registrations.json for persisted records')

    finally:
        if p:
            print('[e2e] terminating started app process')
            try:
                p.terminate()
                time.sleep(1)
            except Exception:
                pass


if __name__ == '__main__':
    main()
