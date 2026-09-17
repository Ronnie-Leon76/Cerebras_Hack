from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache

from . import bc
from .config import DATA_DIR


@lru_cache(maxsize=1)
def _fixtures() -> list[dict]:
    path = DATA_DIR / "site_history.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_for(customer_no: str | None, account_id: str | None = None) -> dict | None:
    for row in _fixtures():
        if customer_no and row.get("customer_no") == customer_no:
            return row
        if account_id and row.get("account_id") == account_id:
            return row
    return None


def load_site_360(account: dict, company: str | None = None) -> dict:
    """Merge Business Central Customer_Card + invoices/quotes with local installed-base history."""
    customer_no = account.get("customer_no") or ""
    company = (company or account.get("country") or "KENYA").upper().replace(" ", "_")
    if company in {"KENYA", "UGANDA", "TANZANIA", "RWANDA", "ZAMBIA", "DRC"}:
        pass
    else:
        company = "KENYA"

    card = bc.get_customer_card(customer_no, company) if customer_no else None
    live_invoices = bc.posted_invoices(customer_no, company) if customer_no else []
    live_quotes = bc.open_quotes(customer_no, company) if customer_no else []
    fx = fixture_for(customer_no, account.get("id")) or {}

    invoices = live_invoices or list(fx.get("invoices") or [])
    quotes = live_quotes or list(fx.get("quotes") or [])
    installed = list(fx.get("installed_base") or [])
    balance = card.get("balance") if card and card.get("balance") is not None else fx.get("balance") or 0

    merged_card = {
        "customer_no": customer_no,
        "name": (card or {}).get("name") or account.get("name"),
        "phone": (card or {}).get("phone") or account.get("phone"),
        "email": (card or {}).get("email") or account.get("email"),
        "address": (card or {}).get("address") or "",
        "city": (card or {}).get("city") or account.get("city"),
        "country": (card or {}).get("country") or account.get("country"),
        "type": account.get("type"),
        "price_group": (card or {}).get("price_group") or fx.get("price_group"),
        "salesperson_code": (card or {}).get("salesperson_code") or fx.get("salesperson_code"),
        "blocked": (card or {}).get("blocked"),
        "balance": balance,
        "credit_limit": (card or {}).get("credit_limit") or fx.get("credit_limit"),
        "responsibility_center": (card or {}).get("responsibility_center"),
        "source": (card or {}).get("source") or ("fixture" if fx else "local"),
    }

    plays = detect_plays(account, installed, invoices, quotes, float(balance or 0))
    return {
        "card": merged_card,
        "installed_base": installed,
        "invoices": invoices,
        "quotes": quotes,
        "plays": plays,
        "live_bc": bool(card or live_invoices or live_quotes),
        "engineer": fx.get("engineer") or account.get("persona_name") or "",
    }


def detect_plays(account: dict, installed: list, invoices: list, quotes: list, balance: float) -> list[dict]:
    today = date.today()
    plays: list[dict] = []
    name = account.get("name") or "Account"

    for asset in installed:
        commissioned = _parse_date(asset.get("commissioned"))
        family = (asset.get("family") or "").lower()
        item = asset.get("item_no") or asset.get("description")
        if commissioned and family == "ro_plant":
            months = _months(commissioned, today)
            if months >= 24:
                plays.append(
                    {
                        "play": "membrane_cycle",
                        "severity": "high",
                        "title": f"Membrane / RO service window — {name}",
                        "body": (
                            f"{item} commissioned {asset.get('commissioned')} ({months} months). "
                            "Proactive visit: membranes, antiscalant, SDI check. Do not requote a new plant first."
                        ),
                    }
                )
        if commissioned and family in {"pretreatment", "disinfection"}:
            months = _months(commissioned, today)
            if months >= 18:
                plays.append(
                    {
                        "play": "media_uv_service",
                        "severity": "medium",
                        "title": f"Media / UV service due — {name}",
                        "body": f"{item} has been in service ~{months} months. Offer media change / UV lamp + residual check.",
                    }
                )

    open_inv = [i for i in invoices if str(i.get("status") or "").lower() in {"open", "overdue"}]
    if open_inv or balance > 0:
        plays.append(
            {
                "play": "collections",
                "severity": "high" if balance > 500000 else "medium",
                "title": f"Open invoices / AR — {name}",
                "body": f"Balance {balance:,.0f}. Coordinate collections before a new BOQ; mention only internally.",
            }
        )

    for q in quotes:
        if str(q.get("status") or "open").lower() == "open":
            plays.append(
                {
                    "play": "quote_followup",
                    "severity": "medium",
                    "title": f"Open quote {q.get('no')} — {name}",
                    "body": q.get("note")
                    or "Quote still open. If water quality changed, re-run sizing from a fresh lab — do not recycle old prices.",
                }
            )

    if installed:
        last_inv = invoices[0].get("date") if invoices else None
        plays.append(
            {
                "play": "installed_site_expansion",
                "severity": "medium",
                "title": f"Existing Dayliff site — expand, don't cold-call — {name}",
                "body": (
                    "This is an installed-base account. Lead with uptime, spares, and a new lab if they want more flow. "
                    f"Last invoice date: {last_inv or 'n/a'}."
                ),
            }
        )

    if not installed and not invoices:
        plays.append(
            {
                "play": "new_logo",
                "severity": "low",
                "title": f"No posted history — treat as new logo — {name}",
                "body": "No invoices or installs on file. Lab-first sizing path. Confirm ERP customer card before quoting.",
            }
        )
    return plays


def persist_notifications(account_id: str, engineer: str, plays: list[dict]) -> int:
    from . import crm

    existing = {(n.get("play"), n.get("title")) for n in crm.list_notifications(account_id=account_id, status="open")}
    created = 0
    for p in plays:
        key = (p.get("play"), p.get("title"))
        if key in existing:
            continue
        crm.add_notification(account_id, engineer, p)
        crm.add_task(account_id, p.get("title") or "Follow up", 3 if p.get("severity") == "high" else 7)
        created += 1
    return created


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _months(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def scan_all_accounts() -> dict:
    from . import crm

    created = 0
    scanned = 0
    for acc in crm.list_accounts():
        scanned += 1
        site = load_site_360(acc)
        created += persist_notifications(
            acc["id"],
            site.get("engineer") or acc.get("persona_name") or "engineer",
            site.get("plays") or [],
        )
        crm.add_activity(acc["id"], "installed_base_scan", f"{len(site.get('plays') or [])} plays")
    return {"scanned": scanned, "alerts_created": created}
