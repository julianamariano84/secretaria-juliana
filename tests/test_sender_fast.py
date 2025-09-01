import os
import types
import pytest

from messaging import sender


def test_fast_path_success(monkeypatch):
    # Enable fast mode and provide env
    monkeypatch.setenv('ZAPI_FAST', '1')
    monkeypatch.setenv('ZAPI_URL', 'https://example.test/send')
    monkeypatch.setenv('ZAPI_TOKEN', 'abc123')

    class DummyResp:
        ok = True
        status_code = 200
        text = '{"status": "ok", "id": "fast-1"}'

        def json(self):
            return {'status': 'ok', 'id': 'fast-1'}

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url == os.getenv('ZAPI_URL')
        assert 'phone' in json
        return DummyResp()

    monkeypatch.setattr(sender, 'requests', types.SimpleNamespace(post=fake_post))

    res = sender.send_text('5511999999999', 'teste fast')
    assert res['status'] == 'ok'
    assert res['id'] == 'fast-1'


def test_fast_path_fail_raises(monkeypatch):
    # Enable fast mode but remote returns non-ok
    monkeypatch.setenv('ZAPI_FAST', '1')
    monkeypatch.setenv('ZAPI_URL', 'https://example.test/send')
    monkeypatch.setenv('ZAPI_TOKEN', 'abc123')

    class DummyResp:
        ok = False
        status_code = 400
        text = 'bad'

    def fake_post(url, json=None, headers=None, timeout=None):
        return DummyResp()

    monkeypatch.setattr(sender, 'requests', types.SimpleNamespace(post=fake_post))

    with pytest.raises(RuntimeError):
        sender.send_text('5511999999999', 'teste fast fail')
