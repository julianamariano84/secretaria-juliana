import os
import json
import time


def make_app():
    # Ensure strict anti-loop env for tests
    os.environ.setdefault('IGNORE_FROM_ME', '1')
    os.environ.setdefault('SPAM_GUARD_SECONDS', '30')
    os.environ.setdefault('ECHO_SUPPRESS_SECONDS', '120')
    os.environ.setdefault('DISABLE_GREETING', '1')
    os.environ.setdefault('ENABLE_SCHEDULER', '0')
    # No Z-API envs -> sender will use stub and persist last_outbound
    from app import create_app
    return create_app()


def _post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), headers={'Content-Type': 'application/json'})


def test_inbound_then_echo_msgid_ignored():
    app = make_app()
    client = app.test_client()
    phone = '5511999999999'

    # First inbound message from user
    p1 = {"message": {"from": phone, "text": "Oi", "id": "abc123"}}
    r1 = _post_json(client, '/webhook/entrada', p1)
    assert r1.status_code == 200
    # Repeat same msg id -> should be ignored by echo_msgid
    r2 = _post_json(client, '/webhook/entrada', p1)
    assert r2.status_code == 200
    body = r2.get_json() or {}
    assert body.get('ignored') in ('echo_msgid', 'duplicate_window', 'non_chat_event')


def test_outbound_echo_ignored_by_text_match():
    app = make_app()
    client = app.test_client()
    phone = '5511888888888'

    # Trigger flow so app sends the first question (stub sender persists last_outbound)
    p1 = {"message": {"from": phone, "text": "Quero me cadastrar", "id": "m1"}}
    r1 = _post_json(client, '/webhook/entrada', p1)
    assert r1.status_code == 200

    # Short sleep to ensure ts differs
    time.sleep(0.1)

    # Simulate provider echoing our last outbound question text back to webhook
    # We don't know exact question text mapping here; use one we configured in handler
    echo_text = 'Qual seu nome completo?'
    p2 = {"message": {"from": phone, "text": echo_text, "id": "m2"}}
    r2 = _post_json(client, '/webhook/entrada', p2)
    assert r2.status_code == 200
    body2 = r2.get_json() or {}
    assert body2.get('ignored') in ('echo_match_outbound', 'fromMe', 'duplicate_window', 'non_chat_event')


def test_duplicate_window_same_text():
    app = make_app()
    client = app.test_client()
    phone = '5511777777777'

    p = {"message": {"from": phone, "text": "Oi", "id": "x1"}}
    r1 = _post_json(client, '/webhook/inbound', p)
    assert r1.status_code == 200
    # send similar payload with a different id but same text immediately
    p2 = {"message": {"from": phone, "text": "oi", "id": "x2"}}
    r2 = _post_json(client, '/webhook/inbound', p2)
    assert r2.status_code == 200
    body = r2.get_json() or {}
    assert body.get('ignored') in ('duplicate_window', 'echo_msgid', 'echo_match_outbound', 'non_chat_event')
