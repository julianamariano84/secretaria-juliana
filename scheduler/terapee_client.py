"""Minimal scaffold adapter for Terapee integrations.

This module provides a small, testable client with two primary operations:
- check_availability(...)
- book_consultation(...)

It intentionally supports a "stub mode" when `TERAPEE_API_URL` and
`TERAPEE_API_TOKEN` are not configured (makes local development safe). When
configured, it will issue HTTP requests to the configured endpoints. Because
Terapee does not provide a public API spec here, the HTTP contract is generic
and easy to mock in tests; adapt the endpoint paths to the real API once you
have documentation or credentials.
"""

from typing import Optional, Dict, Any
import os
import requests


class TerapeeClient:
    def __init__(self, api_url: Optional[str] = None, api_token: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_url = api_url or os.getenv("TERAPEE_API_URL")
        self.api_token = api_token or os.getenv("TERAPEE_API_TOKEN")
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_token)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

    def check_availability(self, professional_id: str, start_iso: str, end_iso: str, service_id: Optional[str] = None, timezone: Optional[str] = None) -> Dict[str, Any]:
        """Check availability for a professional in the given interval.

        Returns a dict: {"available": bool, "reasons": [str]}
        In stub-mode (not configured) returns available=True.
        """
        if not self.configured:
            return {"available": True, "reasons": ["stub mode: assume free"]}

        params = {
            "professional_id": professional_id,
            "start": start_iso,
            "end": end_iso,
        }
        if service_id:
            params["service_id"] = service_id
        if timezone:
            params["timezone"] = timezone

        url = f"{self.api_url.rstrip('/')}/availability"
        resp = self.session.get(url, params=params, headers=self._headers(), timeout=10)
        try:
            resp.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"availability request failed: {e}; body={resp.text}")

        data = resp.json()
        # Expect the API to return a boolean or structured response; normalize it.
        if isinstance(data, dict):
            if "available" in data:
                return {"available": bool(data.get("available")), "reasons": data.get("reasons") or []}
            # fallback: consider any non-empty slots as available
            slots = data.get("slots") or []
            return {"available": bool(slots), "reasons": []}

        # If API returns simple boolean
        if isinstance(data, bool):
            return {"available": data, "reasons": []}

        return {"available": False, "reasons": ["unexpected response"]}

    def book_consultation(self, professional_id: str, patient_id: str, start_iso: str, end_iso: str, service_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Book an appointment.

        Returns: {"success": bool, "booking_id": str|None, "error": str|None}
        In stub-mode returns a fabricated booking id.
        """
        if not self.configured:
            return {"success": True, "booking_id": "stub-" + start_iso, "error": None}

        payload = {
            "professional_id": professional_id,
            "patient_id": patient_id,
            "start": start_iso,
            "end": end_iso,
        }
        if service_id:
            payload["service_id"] = service_id
        if metadata:
            payload["metadata"] = metadata

        url = f"{self.api_url.rstrip('/')}/bookings"
        resp = self.session.post(url, json=payload, headers=self._headers(), timeout=10)
        try:
            resp.raise_for_status()
        except Exception as e:
            # return structured error
            return {"success": False, "booking_id": None, "error": f"request failed: {e}; body={resp.text}"}

        data = resp.json()
        # normalize expected shape
        booking_id = data.get("booking_id") or data.get("id") or data.get("appointment_id")
        return {"success": True, "booking_id": booking_id, "error": None, "raw": data}
