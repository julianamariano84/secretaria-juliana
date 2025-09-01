from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from typing import Dict, Any, Optional

# ...existing code...

def _job():
    print(f"[{datetime.utcnow().isoformat()}] Scheduler heartbeat")

def init_scheduler(app=None):
    sched = BackgroundScheduler()
    try:
        interval = int(app.config.get("SCHED_INTERVAL", 60)) if app else 60
    except Exception:
        interval = 60
    sched.add_job(_job, "interval", seconds=interval, id="heartbeat", replace_existing=True)
    sched.start()
    return sched

def schedule_consultation(data: dict) -> dict:
    # Minimal stub: in production persist to DB and schedule reminders
    print(f"[stub] Scheduling consultation: {data}")
    return {"scheduled": True, "data": data}


# Terapee integration scaffold
try:
    from .terapee_client import TerapeeClient
except Exception:
    TerapeeClient = None
try:
    from .terapee_scraper import TerapeeScraper
except Exception:
    TerapeeScraper = None


def check_availability(professional_id: str, start_iso: str, end_iso: str, service_id: Optional[str] = None, timezone: Optional[str] = None) -> Dict[str, Any]:
    """Check availability using TerapeeClient if configured; otherwise return stub (available=True).

    Returns: {"available": bool, "reasons": [str]}
    """
    if TerapeeClient is None:
        return {"available": True, "reasons": ["terapee client not available"]}

    client = TerapeeClient()
    return client.check_availability(professional_id, start_iso, end_iso, service_id=service_id, timezone=timezone)


def check_availability_via_ui(professional_id: str, start_iso: str, end_iso: str, service_id: Optional[str] = None, timezone: Optional[str] = None) -> Dict[str, Any]:
    """Attempt to check availability via UI automation (scraper) if configured.

    Falls back to stub (available=True) when the scraper is not configured.
    """
    if TerapeeScraper is None:
        return {"available": True, "reasons": ["scraper not available"]}

    s = TerapeeScraper()
    return s.check_availability(professional_id, start_iso, end_iso, service_id=service_id, timezone=timezone)


def book_consultation_terapee(professional_id: str, patient_id: str, start_iso: str, end_iso: str, service_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Book a consultation via TerapeeClient. Returns normalized result.

    Returns {"success": bool, "booking_id": str|None, "error": str|None}
    """
    if TerapeeClient is None:
        return {"success": True, "booking_id": f"stub-{start_iso}", "error": None}

    client = TerapeeClient()
    return client.book_consultation(professional_id, patient_id, start_iso, end_iso, service_id=service_id, metadata=metadata)
