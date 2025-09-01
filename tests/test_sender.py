import os
import types
import pytest

from messaging import sender


def test_stub_send(monkeypatch):
    # Ensure no ZAPI config
    monkeypatch.delenv("ZAPI_URL", raising=False)
    monkeypatch.delenv("ZAPI_TOKEN", raising=False)
    monkeypatch.delenv("ZAP_TOKEN", raising=False)
    monkeypatch.delenv("CLIENT_TOKEN", raising=False)

    res = sender.send_text("5511999999999", "teste stub")
    assert res["status"] == "sent (stub)"
    assert res["to"] == "5511999999999"


def test_partial_config_raises(monkeypatch):
    # Set only token
    monkeypatch.setenv("ZAPI_TOKEN", "tok")
    monkeypatch.delenv("ZAP_TOKEN", raising=False)
    monkeypatch.delenv("ZAPI_URL", raising=False)

    with pytest.raises(RuntimeError):
        sender.send_text("5511999999999", "mensagem")


def test_real_send_success(monkeypatch):
    # Provide both env vars and patch requests.post
    monkeypatch.setenv("ZAPI_URL", "https://example.test/send")
    monkeypatch.setenv("ZAPI_TOKEN", "abc123")
    monkeypatch.delenv("ZAP_TOKEN", raising=False)
    monkeypatch.delenv("CLIENT_TOKEN", raising=False)

    class DummyResp:
        ok = True
        status_code = 200
        text = '{"status": "ok", "id": "123"}'

        def json(self):
            return {"status": "ok", "id": "123"}

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url == os.getenv("ZAPI_URL")
        assert headers["Authorization"].startswith("Bearer ")
        return DummyResp()

    monkeypatch.setattr(sender, "requests", types.SimpleNamespace(post=fake_post))

    res = sender.send_text("5511999999999", "mensagem real")
    assert res["status"] == "ok"
    assert res["id"] == "123"
