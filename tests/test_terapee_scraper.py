import pytest
from scheduler.terapee_scraper import TerapeeScraper


def test_scraper_stub_mode(monkeypatch):
    monkeypatch.delenv("TERAPEE_BASE_URL", raising=False)
    monkeypatch.delenv("TERAPEE_UI_USER", raising=False)
    monkeypatch.delenv("TERAPEE_UI_PASS", raising=False)

    s = TerapeeScraper()
    assert s.configured is False

    av = s.check_availability("p1", "2025-09-01T10:00:00Z", "2025-09-01T11:00:00Z")
    assert av["available"] is True

    bk = s.book_consultation("p1", "Paciente Teste", "2025-09-01T10:00:00Z", "2025-09-01T11:00:00Z")
    assert bk["success"] is True
    assert bk["booking_id"].startswith("stub-")


def test_login_requires_playwright(monkeypatch):
    # Ensure credentials are present so scraper tries to use Playwright
    monkeypatch.setenv("TERAPEE_BASE_URL", "https://app.terapee.com.br")
    monkeypatch.setenv("TERAPEE_UI_USER", "user@example.com")
    monkeypatch.setenv("TERAPEE_UI_PASS", "password")

    s = TerapeeScraper()
    with pytest.raises(RuntimeError):
        s.login()
