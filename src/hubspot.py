from __future__ import annotations

from typing import Any

import httpx

from .config import hubspot_token


def enabled() -> bool:
    return bool(hubspot_token())


def search_companies(query: str) -> list[dict]:
    if not enabled() or not query.strip():
        return []
    try:
        r = httpx.post(
            "https://api.hubapi.com/crm/v3/objects/companies/search",
            headers=_headers(),
            json={
                "query": query.strip(),
                "limit": 8,
                "properties": ["name", "domain", "city", "country", "industry", "phone"],
            },
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json().get("results") or []
    except Exception:
        return []


def upsert_note(company_id: str, body: str) -> dict[str, Any]:
    if not enabled():
        return {"ok": False, "reason": "HubSpot not configured"}
    try:
        r = httpx.post(
            "https://api.hubapi.com/crm/v3/objects/notes",
            headers=_headers(),
            json={"properties": {"hs_note_body": body, "hs_timestamp": None}},
            timeout=15.0,
        )
        r.raise_for_status()
        note = r.json()
        nid = note.get("id")
        if nid and company_id:
            httpx.put(
                f"https://api.hubapi.com/crm/v3/objects/notes/{nid}/associations/companies/{company_id}/note_to_company",
                headers=_headers(),
                timeout=15.0,
            )
        return {"ok": True, "id": nid}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {hubspot_token()}", "Content-Type": "application/json"}
