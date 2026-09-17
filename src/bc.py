from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .config import bc_password, bc_url, bc_username


def _enc(filter_expr: str) -> str:
    return quote(filter_expr, safe="")


def configured() -> bool:
    return bool(bc_url() and bc_username() and bc_password())


def _company_url(company: str) -> str:
    base = bc_url()
    company = (company or "KENYA").upper()
    if "Company(" in base:
        import re

        return re.sub(r"Company\('[^']*'\)", f"Company('{company}')", base).rstrip("/")
    return f"{base}/Company('{company}')"


def _client() -> httpx.Client:
    return httpx.Client(
        auth=(bc_username(), bc_password()),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=20.0,
    )


def _get(path: str, company: str) -> dict | None:
    if not configured():
        return None
    url = f"{_company_url(company)}{path if path.startswith('/') else '/' + path}"
    try:
        with _client() as client:
            r = client.get(url)
            if r.status_code >= 400:
                return None
            return r.json()
    except Exception:
        return None


def _values(data: dict | None) -> list[dict]:
    if not data:
        return []
    if isinstance(data.get("value"), list):
        return [x for x in data["value"] if isinstance(x, dict)]
    if isinstance(data, dict) and data.get("No"):
        return [data]
    return []


def search_customer_card(term: str, company: str = "KENYA", take: int = 20) -> list[dict]:
    """Same Customer_Card OData surface as sizing `business-central.ts`."""
    safe = (term or "").replace("'", "''").strip()
    if not safe or not configured():
        return []
    seen: dict[str, dict] = {}

    def add(rows: list[dict]) -> None:
        for row in rows:
            mapped = _map_card(row)
            no = mapped.get("customer_no")
            if no and no not in seen:
                seen[no] = mapped

    eq_no = _enc(f"No eq '{safe}'")
    phone = _enc(f"contains(Phone_No,'{safe}')")
    name = _enc(f"contains(Name,'{safe}')")
    add(_values(_get(f"/Customer_Card?$filter={eq_no}&$top=10", company)))
    add(_values(_get(f"/Customer_Card?$filter={phone}&$top=10", company)))
    add(_values(_get(f"/Customer_Card?$filter={name}&$top={take}", company)))
    return list(seen.values())[:take]


def get_customer_card(customer_no: str, company: str = "KENYA") -> dict | None:
    safe = (customer_no or "").replace("'", "''").strip()
    if not safe:
        return None
    filt = _enc(f"No eq '{safe}'")
    rows = _values(_get(f"/Customer_Card?$filter={filt}&$top=1", company))
    return _map_card(rows[0]) if rows else None


def posted_invoices(customer_no: str, company: str = "KENYA") -> list[dict]:
    safe = (customer_no or "").replace("'", "''").strip()
    if not safe or not configured():
        return []
    filt = _enc(f"Sell_to_Customer_No eq '{safe}'")
    for entity in (
        f"/Posted_Sales_Invoice?$filter={filt}&$top=40&$orderby=Posting_Date desc",
        f"/PostedSalesInvoices?$filter={filt}&$top=40",
        f"/SalesInvoice?$filter={filt}&$top=40",
    ):
        rows = _values(_get(entity, company))
        if rows:
            return [_map_invoice(r) for r in rows]
    return []


def open_quotes(customer_no: str, company: str = "KENYA") -> list[dict]:
    safe = (customer_no or "").replace("'", "''").strip()
    if not safe or not configured():
        return []
    filt = _enc(f"Sell_to_Customer_No eq '{safe}'")
    rows = _values(_get(f"/Sales_Quote?$filter={filt}&$top=20", company))
    return [
        {
            "no": r.get("No"),
            "date": r.get("Document_Date") or r.get("Order_Date"),
            "status": r.get("Status") or "open",
            "amount": r.get("Amount_Including_VAT") or r.get("Amount"),
            "note": r.get("External_Document_No") or "",
        }
        for r in rows
    ]


def _map_card(c: dict[str, Any]) -> dict:
    addr = c.get("Address") or ""
    addr2 = c.get("Address_2") or ""
    city = c.get("City") or ""
    post = c.get("Post_Code") or ""
    full = ", ".join(x for x in (addr, addr2, city, post) if x) or addr or city
    return {
        "customer_no": c.get("No") or c.get("customer_no"),
        "name": c.get("Name") or c.get("customer_name"),
        "phone": c.get("Phone_No") or c.get("phone_no"),
        "email": c.get("E_Mail") or c.get("email"),
        "address": full,
        "city": city,
        "county": c.get("County"),
        "post_code": post,
        "country": c.get("Country_Region_Code") or c.get("country"),
        "salesperson_code": c.get("Salesperson_Code"),
        "responsibility_center": c.get("Responsibility_Center"),
        "price_group": c.get("Customer_Price_Group"),
        "disc_group": c.get("Customer_Disc_Group"),
        "customer_posting_group": c.get("Customer_Posting_Group"),
        "customer_status": c.get("Customer_Status"),
        "blocked": c.get("Blocked"),
        "balance": c.get("Balance_LCY"),
        "credit_limit": c.get("Credit_Limit_LCY"),
        "source": "bc_customer_card",
    }


def _map_invoice(r: dict[str, Any]) -> dict:
    return {
        "no": r.get("No") or r.get("Document_No"),
        "date": r.get("Posting_Date") or r.get("Document_Date"),
        "amount": r.get("Amount_Including_VAT") or r.get("Amount"),
        "currency": r.get("Currency_Code") or "LCY",
        "status": "open" if r.get("Closed") is False else "paid",
        "lines": [],
        "source": "bc",
    }
