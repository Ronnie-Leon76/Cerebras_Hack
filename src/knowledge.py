from __future__ import annotations

import json
from functools import lru_cache

from .config import DATA_DIR


@lru_cache(maxsize=1)
def icp() -> dict:
    return json.loads((DATA_DIR / "icp.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def claims() -> dict:
    return json.loads((DATA_DIR / "claims.json").read_text(encoding="utf-8"))


def voice() -> str:
    return (DATA_DIR / "voice.md").read_text(encoding="utf-8")


def web_research(company: str, domain: str | None = None) -> list[dict]:
    query = f"{company} {domain or ''} East Africa water energy".strip()
    try:
        from ddgs import DDGS

        hits = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=5):
                hits.append(
                    {
                        "title": item.get("title") or "",
                        "href": item.get("href") or "",
                        "body": item.get("body") or "",
                    }
                )
        return hits
    except Exception:
        return []


def match_use_cases(account: dict) -> list[dict]:
    blob = " ".join(
        [
            str(account.get("name") or ""),
            str(account.get("segment") or ""),
            str(account.get("type") or ""),
            str(account.get("notes") or ""),
            " ".join(account.get("signals") or []),
        ]
    ).lower()
    patterns = icp().get("use_case_patterns") or []
    scored = []
    for p in patterns:
        tokens = [t.lower() for t in (p.get("signals") or p.get("keywords") or [])]
        if not tokens:
            tokens = [str(p.get("id") or ""), str(p.get("name") or "")]
        hits = [t for t in tokens if t and t.lower() in blob]
        score = len(hits)
        if account.get("segment") and account.get("segment") in str(p.get("segments") or []):
            score += 2
        if score:
            scored.append({**p, "score": score, "matched": hits})
    scored.sort(key=lambda x: -x["score"])
    return scored[:3]


LAB_ASK = {
    "borehole_ro": [
        "TDS / conductivity",
        "pH",
        "hardness",
        "iron",
        "manganese",
        "turbidity / SDI",
        "free chlorine",
        "required permeate m³/hr",
    ],
    "pharma_pw": [
        "feed conductivity",
        "TOC (if available)",
        "hardness / silica",
        "micro / endotoxin if specified",
        "required PW m³/hr and Ph. Eur. / USP target",
        "sanitization / PLC preference",
    ],
    "media_iron": ["iron", "manganese", "turbidity", "pH", "TDS", "flow m³/hr"],
    "solar_pumping": ["static/dynamic water level", "duty flow", "diesel hours", "TDS if treating"],
    "hospital_disinfection": ["free chlorine residual", "turbidity", "TDS", "dialysis/CSSD spec if any"],
    "_default": ["TDS / conductivity", "pH", "hardness", "iron", "turbidity", "required flow"],
}


def choose_technology(account: dict, use_cases: list[dict]) -> str:
    blob = " ".join(
        [
            str(account.get("segment") or ""),
            str(account.get("notes") or ""),
            " ".join(account.get("signals") or []),
            " ".join(str(u.get("id") or "") for u in use_cases),
        ]
    ).lower()
    if any(k in blob for k in ("uf", "ultrafilt")) and "tds" not in blob and "brackish" not in blob:
        return "uf"
    if any(k in blob for k in ("pharma", "pw", "ro", "brackish", "tds", "bottl", "borehole")):
        return "ro"
    if use_cases and use_cases[0].get("lead_family") == "ro_plant":
        return "ro"
    return "either"


def build_sizing_handoff(account: dict, use_cases: list[dict], products: list) -> "SizingHandoff":
    from .config import sizing_base_url
    from .models import SizingHandoff

    base = sizing_base_url()
    tech = choose_technology(account, use_cases)
    uc_id = (use_cases[0].get("id") if use_cases else "") or "_default"
    lab = list(LAB_ASK.get(uc_id) or LAB_ASK["_default"])
    path = "uf" if tech == "uf" else "ro"
    skus = []
    for p in products[:5]:
        if hasattr(p, "item_no"):
            skus.append(f"{p.item_no} ({p.family})")
        elif isinstance(p, dict):
            skus.append(str(p.get("item_no") or ""))
    card = {
        "customerNo": account.get("customer_no") or "",
        "name": account.get("name") or "",
        "phone": account.get("phone") or "",
        "email": account.get("email") or "",
        "city": account.get("city") or "",
        "country": account.get("country") or "",
        "type": account.get("type") or "INDUSTRIAL",
        "contactName": account.get("persona_name") or "",
        "notes": account.get("notes") or "",
    }
    prompt = (
        f"Open {path.upper()} in AI Product Sizing. Attach a lab analysis (not a spec sheet). "
        f"Select ERP customer {card['customerNo'] or card['name']}. "
        f"Do not invent Economy/Standard/Premium BOQ until parameters extract. "
        f"Hypothesized SKUs for the SDR only: {', '.join(skus) or 'catalogue after lab'}."
    )
    return SizingHandoff(
        technology=tech,  # type: ignore[arg-type]
        sizing_url=f"{base}/dashboard/water-treatment/{path}",
        lab_reports_url=f"{base}/dashboard/water-treatment/{path}/lab-reports",
        customers_url=f"{base}/dashboard/water-treatment/customers",
        lab_ask=lab,
        option_framing=(
            "Sizing produces three options (Economy, Standard, Premium) plus a BC quote and Word proposal. "
            "Account Prep must never quote those totals."
        ),
        do_not_quote=[
            "No unit prices in outbound copy",
            "No recovery / permeate conductivity promises",
            "Cylindrical tanks follow sizing commercial policy",
        ],
        customer_card=card,
        engineer_prompt=prompt,
    )
