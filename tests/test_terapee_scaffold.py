import os
import json
import pytest
from scheduler.terapee_client import TerapeeClient


def test_stub_availability_and_booking(monkeypatch):
    # Ensure env not configured
    monkeypatch.delenv("TERAPEE_API_URL", raising=False)
    monkeypatch.delenv("TERAPEE_API_TOKEN", raising=False)

    client = TerapeeClient()
    av = client.check_availability("p1", "2025-09-01T10:00:00Z", "2025-09-01T11:00:00Z")
    assert av["available"] is True

    bk = client.book_consultation("p1", "pat1", "2025-09-01T10:00:00Z", "2025-09-01T11:00:00Z")
    assert bk["success"] is True
    assert bk["booking_id"].startswith("stub-")


def test_api_calls_mocked(monkeypatch):
    # Provide dummy api_url/token
    monkeypatch.setenv("TERAPEE_API_URL", "https://api.terapee.local")
    monkeypatch.setenv("TERAPEE_API_TOKEN", "sekret")

    class DummyResp:
        def __init__(self, json_data, status=200):
            self._json = json_data
            self.status_code = status
            self.text = json.dumps(json_data)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"status {self.status_code}")

        def json(self):
            return self._json

    # monkeypatch a session with predictable responses
    class DummySession:
        def get(self, url, params=None, headers=None, timeout=None):
            return DummyResp({"available": True})

        def post(self, url, json=None, headers=None, timeout=None):
            return DummyResp({"booking_id": "real-123"})

    client = TerapeeClient(session=DummySession())
    av = client.check_availability("p1", "2025-09-01T10:00:00Z", "2025-09-01T11:00:00Z")
    assert av["available"] is True

    bk = client.book_consultation("p1", "pat1", "2025-09-01T10:00:00Z", "2025-09-01T11:00:00Z")
    assert bk["success"] is True
    assert bk["booking_id"] == "real-123"
