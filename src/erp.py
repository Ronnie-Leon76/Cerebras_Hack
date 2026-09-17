from __future__ import annotations

from typing import Any

import httpx

from .config import microservice_api_key, microservice_url


def search_erp_customers(q: str, limit: int = 20, country: str = "KENYA") -> list[dict]:
    """Same contract as sizing: POST /api/v1/customers/erp/search."""
    base = microservice_url()
    if not base or not q.strip():
        return []
    headers = {"Content-Type": "application/json"}
    key = microservice_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "search_term": q.strip(),
        "search_by": "all",
        "max_results": min(max(limit, 1), 50),
        "country": (country or "KENYA").upper(),
    }
    paths = (
        "/api/v1/customers/erp/search",
        "/customers/erp/search",
        "/api/customers/search",
    )
    last_error = None
    for path in paths:
        try:
            r = httpx.post(f"{base}{path}", json=payload, headers=headers, timeout=15.0)
            if r.status_code >= 400:
                last_error = r.text
                continue
            data = r.json()
            rows = _extract_rows(data)
            if rows:
                return rows
        except Exception as exc:
            last_error = str(exc)
    if last_error:
        return []
    return []


def _extract_rows(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [_normalize(x) for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key_name in ("data", "customers", "value", "items", "results"):
        if isinstance(data.get(key_name), list):
            return [_normalize(x) for x in data[key_name] if isinstance(x, dict)]
    return []


def _normalize(row: dict[str, Any]) -> dict:
    return {
        "customer_no": str(
            row.get("customer_no")
            or row.get("customerNo")
            or row.get("no")
            or row.get("number")
            or ""
        ),
        "name": str(row.get("customer_name") or row.get("name") or row.get("displayName") or ""),
        "phone": str(row.get("phone_no") or row.get("phoneNo") or row.get("phone") or ""),
        "email": str(row.get("email") or ""),
        "address": str(row.get("address") or ""),
        "city": str(row.get("city") or ""),
        "country": str(row.get("country") or row.get("countryRegionCode") or ""),
        "type": str(row.get("type") or row.get("customerType") or ""),
        "price_group": str(row.get("priceGroup") or row.get("price_group") or ""),
    }
