from playwright.sync_api import sync_playwright
import pytest


@pytest.fixture(scope="session", autouse=True)
def _playwright_session():
    """
    Start Playwright once per test session and ensure it is stopped at the end.
    This prevents pending asyncio tasks and unclosed transports reported by pytest.
    """
    pw = sync_playwright().start()
    yield pw
    try:
        pw.stop()
    except Exception:
        # Best-effort cleanup; avoid failing the test teardown
        pass
