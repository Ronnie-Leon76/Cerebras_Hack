from __future__ import annotations

import html
import re
from typing import Iterable, Sequence, TypeVar

import streamlit as st

T = TypeVar("T")

PAGES = [
    "Command",
    "Site 360",
    "Alerts",
    "Run prep",
    "Drafts",
    "Sizing tickets",
    "Catalogue",
    "Pitch",
    "Governance",
]

# Pipeline stages. Clicking a stage calls goto(nav). Quote is created in
# sizing.dayliff.com; we land on Sizing tickets so the engineer still sees the handoff.
STAGES: list[dict[str, str]] = [
    {
        "id": "signal",
        "num": "01",
        "label": "Signal",
        "nav": "Alerts",
        "hint": "Spot accounts that need a human",
    },
    {
        "id": "prep",
        "num": "02",
        "label": "Prep",
        "nav": "Run prep",
        "hint": "AI researches and drafts",
    },
    {
        "id": "gate",
        "num": "03",
        "label": "Human Gate",
        "nav": "Drafts",
        "hint": "Nothing sends until you approve",
    },
    {
        "id": "size",
        "num": "04",
        "label": "Size",
        "nav": "Sizing tickets",
        "hint": "Lab-first ticket for the engineer",
    },
    {
        "id": "quote",
        "num": "05",
        "label": "Quote",
        "nav": "Sizing tickets",
        "hint": "BOQ lives in sizing.dayliff.com",
    },
]

PAGE_STAGE: dict[str, str | None] = {
    "Command": None,
    "Site 360": "signal",
    "Alerts": "signal",
    "Run prep": "prep",
    "Drafts": "gate",
    "Sizing tickets": "size",
    "Catalogue": "quote",
    "Pitch": None,
    "Governance": None,
}

PAGE_WHY: dict[str, str] = {
    "Command": "Home base: see where the funnel needs a human, then jump into research, drafts, or a sizing ticket.",
    "Site 360": "Look up a customer the same way sizing does — Customer_Card, invoices, installed plant — so outreach is never written as if they were a new logo.",
    "Alerts": "The system scanned every installed account and flagged ones needing proactive engineer attention — service windows, aging equipment, or overdue invoices.",
    "Run prep": "Run the AI crew on one account. You get a research brief, draft outreach, and a sizing ticket — drafts never send from here.",
    "Drafts": "This is the human gate. Edit tone if needed, then approve; approval marks copy as SDR-ready and does not send email or LinkedIn.",
    "Sizing tickets": "Packets for the engineer. The lab PDF and the real BOQ / quote still happen in AI Product Sizing, never in this app.",
    "Catalogue": "Internal Dayliff families the mapper can hypothesize. Prices stay hidden; the live quote is built in sizing after a lab report.",
    "Pitch": "The business case for a 30-day draft-only pilot — time returned, aftermarket plays, and quote integrity — without claiming auto-send or replacing engineers.",
    "Governance": "What the crew is allowed to write, which systems are live, and the audit trail. Quotes, deal stage, and forecasts stay with the rep and sizing.",
}

# Add new jargon here; with_glossary() and term() pick it up automatically.
GLOSSARY: dict[str, str] = {
    "SDR": "Sales Development Representative — the person who researches accounts and drafts first-touch outreach. This tool is their copilot.",
    "BOQ": "Bill of Quantities — the priced equipment list that becomes a customer quote. Created only in AI Product Sizing, never in this app.",
    "Business Central": "Davis & Shirtliff’s ERP (enterprise resource planning) system. Source of truth for customers, invoices, and quotes.",
    "BC company": "Which country company in Business Central to search (Kenya, Uganda, Tanzania, Rwanda, Zambia, DRC).",
    "BC": "Business Central — D&S’s ERP. Customer cards, invoices, and quotes live here.",
    "Customer_Card": "The Business Central customer record (name, phone, customer number, credit). Same OData page AI Product Sizing uses.",
    "DRO": "Dayliff Reverse Osmosis — a branded RO plant already installed at a site. An old DRO is usually a service / membrane play, not a greenfield sale.",
    "RO": "Reverse Osmosis — membrane process that demineralizes water. Sized in AI Product Sizing after a lab report.",
    "UF": "Ultrafiltration — membrane process that removes particles and microbes; often paired with or compared to RO.",
    "NRW": "Non-Revenue Water — treated water lost or unbilled in a municipal network. A common D&S municipal conversation.",
    "AR": "Accounts receivable — unpaid invoices. Visible to the engineer internally; never put overdue balances in customer-facing drafts.",
    "ICP": "Ideal customer profile — the segments and regions D&S actually wants to pursue.",
    "SKU": "Stock keeping unit — a catalogue item number (e.g. a DRO model or a UV lamp).",
    "FAT": "Factory acceptance test — the plant is checked before shipment. Wrong sizing shows up here.",
    "ERP": "Enterprise resource planning — here, Business Central plus any customer microservice.",
    "OData": "The API style Business Central exposes. Customer_Card is read the same way as in AI Product Sizing.",
    "LangGraph": "The orchestration that runs research → pains → catalogue → drafts → sizing ticket as one crew, with gates.",
    "Cerebras": "The inference host for the Qwen model that writes research and drafts.",
    "Dayliff": "D&S product brand for water treatment, pumping, and related equipment.",
    "AI Product Sizing": "The engineer tool at sizing.dayliff.com. Lab PDF in, Economy / Standard / Premium out, then a BC quote.",
    "Ph. Eur.": "European Pharmacopoeia water-quality parameters often requested for pharma / high-purity sites.",
}

_GLOSSARY_KEYS = sorted(GLOSSARY.keys(), key=len, reverse=True)
_GLOSSARY_PARTS = []
for _k in _GLOSSARY_KEYS:
    _esc = re.escape(_k)
    if re.search(r"[^\w]", _k):
        _GLOSSARY_PARTS.append(_esc)
    else:
        _GLOSSARY_PARTS.append(rf"\b{_esc}\b")
_GLOSSARY_PARTS.append(r"\bSQ-\d{2}-\d{3,}\b")
_GLOSSARY_RE = re.compile("|".join(_GLOSSARY_PARTS), re.IGNORECASE)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap');

html, body, [data-testid="stAppViewContainer"] {
  font-family: 'DM Sans', sans-serif;
  background: radial-gradient(1200px 500px at 10% -10%, #d7ecf8 0%, transparent 55%),
              radial-gradient(900px 400px at 100% 0%, #e8f4fb 0%, transparent 50%),
              #F3F7FB;
}
.block-container { padding-top: 0.6rem; max-width: 1240px; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #00263d 0%, #014a73 100%);
}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
  color: #e7f4fc !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  padding: 8px 10px !important;
  margin-bottom: 6px;
}
[data-testid="stSidebar"] [data-baseweb="radio"] {
  background: transparent;
}

.hero {
  background: linear-gradient(120deg, #00263d 0%, #007AC2 62%, #5ec0ee 140%);
  border-radius: 22px;
  padding: 18px 24px 16px;
  color: #fff;
  margin-bottom: 0.85rem;
  box-shadow: 0 22px 50px rgba(0, 50, 77, 0.24);
  position: relative;
  overflow: hidden;
}
.hero:after {
  content: "";
  position: absolute; right: -40px; top: -50px;
  width: 220px; height: 220px; border-radius: 50%;
  background: rgba(255,255,255,0.08);
}
.hero h1 {
  font-family: Fraunces, Georgia, serif;
  font-size: 1.7rem; font-weight: 560; margin: 0 0 6px;
  letter-spacing: -0.03em;
}
.hero p { margin: 0; opacity: 0.93; max-width: 820px; font-size: 0.95rem; }
.pills { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.pill {
  background: rgba(255,255,255,0.14);
  border: 1px solid rgba(255,255,255,0.28);
  border-radius: 999px; padding: 4px 11px; font-size: 0.74rem;
}

.page-title {
  font-family: Fraunces, Georgia, serif;
  font-size: 1.65rem; font-weight: 560; color: #0B1F33;
  margin: 0 0 4px; letter-spacing: -0.02em;
}
.why {
  color: #5d7386; font-size: 0.95rem; line-height: 1.45;
  margin: 0 0 1rem; max-width: 820px;
}

.kpi {
  background: #fff; border: 1px solid #d5e6f2; border-radius: 16px;
  padding: 14px 16px 12px; box-shadow: 0 10px 24px rgba(11,31,51,0.05);
  height: 100%;
}
.kpi .n { font-family: Fraunces, Georgia, serif; font-size: 1.75rem; color: #00324d; line-height: 1; }
.kpi .l { color: #3d5568; font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 6px; }
.kpi .c { color: #5d7386; font-size: 0.78rem; line-height: 1.35; margin-top: 8px; }
.rail {
  height: 4px; border-radius: 4px 4px 0 0; margin: 8px 0 -8px;
}
.rail-ai { background: #007AC2; }
.rail-ok { background: #1a8a4a; }
.rail-no { background: #8a5a00; }

.acc-card, .ticket, .insight-card {
  background: #fff; border: 1px solid #d5e6f2; border-radius: 16px;
  padding: 14px 16px; margin-bottom: 10px;
  box-shadow: 0 8px 18px rgba(11,31,51,0.04);
}
.acc-card h4, .insight-card h4 { margin: 0 0 4px; font-size: 1.02rem; color: #0B1F33; }
.insight-card .ico { font-size: 1.1rem; margin-right: 6px; }
.muted { color: #5d7386; font-size: 0.84rem; }
.badge { display: inline-block; border-radius: 6px; padding: 2px 8px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }
.badge-high { background: #d9f3e3; color: #0d6b3c; }
.badge-medium { background: #fff3d6; color: #8a5a00; }
.badge-low { background: #f1f4f7; color: #4a6072; }
.badge-ro { background: #e6f3fb; color: #007AC2; }
.badge-uf { background: #ece8fb; color: #5b3cc4; }
.badge-ai { background: #e6f3fb; color: #014a73; }
.badge-ok { background: #d9f3e3; color: #0d6b3c; }

.ai-pane, .ok-pane, .draft-box {
  white-space: pre-wrap; font-size: 0.92rem; line-height: 1.5;
  border-radius: 12px; padding: 12px 14px; margin: 6px 0 12px;
}
.ai-pane, .draft-box {
  background: #f6fbfe; border: 1px solid #c5dff0; border-left: 4px solid #007AC2;
}
.ok-pane {
  background: #f4fbf6; border: 1px solid #c6e6d2; border-left: 4px solid #1a8a4a;
}
.pane-label { margin-bottom: 8px; }

.term {
  border-bottom: 1px dotted #007AC2;
  cursor: help;
  position: relative;
  white-space: nowrap;
}
.term .tip {
  display: none;
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  width: min(280px, 70vw);
  white-space: normal;
  background: #00263d;
  color: #e7f4fc;
  font-size: 0.78rem;
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
  line-height: 1.4;
  padding: 8px 10px;
  border-radius: 8px;
  z-index: 80;
  box-shadow: 0 12px 28px rgba(0,38,61,0.28);
}
.term:hover .tip, .term:focus .tip, .term:focus-within .tip { display: block; }

.legend-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 4px 0 8px; }
.legend-chip {
  background: #fff; border: 1px solid #d5e6f2; border-radius: 999px;
  padding: 3px 10px; font-size: 0.75rem; color: #3d5568;
}
.dl-grid { display: grid; grid-template-columns: 160px 1fr; gap: 6px 12px; font-size: 0.9rem; }
.dl-grid dt { color: #5d7386; }
.dl-grid dd { margin: 0; color: #0B1F33; }
.pagebar { color: #5d7386; font-size: 0.85rem; margin: 4px 0 10px; }
.trust { font-size: 0.8rem; color: #b7d3e6; }
.pipe-note { color: #5d7386; font-size: 0.78rem; margin: -4px 0 12px; }
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def goto(page: str) -> None:
    if page not in PAGES:
        return
    st.session_state["nav_radio"] = page
    st.rerun()


def tooltip_html(label: str, definition: str | None = None) -> str:
    definition = definition or GLOSSARY.get(label) or GLOSSARY.get(label.upper())
    if not definition and label.upper().startswith("SQ-"):
        definition = (
            "A Business Central sales-quote number (SQ-year-sequence). "
            "Open quotes belong in Site 360; new quotes are created in AI Product Sizing."
        )
    if not definition:
        return label
    safe_def = (
        definition.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
    safe_lab = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<span class="term" tabindex="0" title="{safe_def}">{safe_lab}'
        f'<span class="tip">{safe_def}</span></span>'
    )


def term(key: str) -> str:
    """HTML for a glossary term. Use inside st.markdown(..., unsafe_allow_html=True)."""
    return tooltip_html(key, GLOSSARY.get(key))


def with_glossary(text: str) -> str:
    """Wrap known jargon in hover tooltips. Safe to run on plain-English copy."""
    if not text:
        return text

    def repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        for key, definition in GLOSSARY.items():
            if raw.lower() == key.lower():
                return tooltip_html(raw, definition)
        return tooltip_html(raw)

    return _GLOSSARY_RE.sub(repl, text)


def page_header(title: str, why: str | None = None) -> None:
    explainer = why if why is not None else PAGE_WHY.get(title, "")
    st.markdown(
        f'<h2 class="page-title">{title}</h2><p class="why">{with_glossary(explainer)}</p>',
        unsafe_allow_html=True,
    )


def resolve_stage(nav: str) -> str | None:
    """Prefer a stepper click when it still matches this page; else map from nav."""
    focus = st.session_state.get("pipeline_focus")
    by_id = {s["id"]: s for s in STAGES}
    if focus in by_id and by_id[focus]["nav"] == nav:
        return str(focus)
    if focus and (focus not in by_id or by_id[focus]["nav"] != nav):
        st.session_state.pop("pipeline_focus", None)
    return PAGE_STAGE.get(nav)


def pipeline_stepper(current_id: str | None = None) -> None:
    """Interactive 5-stage funnel. Visible on every page."""
    order = [s["id"] for s in STAGES]
    cur_idx = order.index(current_id) if current_id in order else -1
    cols = st.columns(5)
    for i, (col, stage) in enumerate(zip(cols, STAGES)):
        done = 0 <= i < cur_idx
        here = i == cur_idx
        mark = "✓ " if done else f"{stage['num']} "
        short = "Gate" if stage["id"] == "gate" else stage["label"]
        label = f"{mark}{short}"
        btn_type = "primary" if here else "secondary"
        if col.button(label, key=f"pipe_{stage['id']}", type=btn_type, use_container_width=True):
            st.session_state["pipeline_focus"] = stage["id"]
            if stage["id"] == "quote":
                st.session_state["quote_hint"] = True
            goto(stage["nav"])
        if current_id is None:
            col.caption(stage["hint"])
    st.markdown(
        '<p class="pipe-note">Signal → Prep → Human gate → Size → Quote. '
        "This app stops at the sizing ticket; the "
        + term("BOQ")
        + " is built in "
        + term("AI Product Sizing")
        + ".</p>",
        unsafe_allow_html=True,
    )
    if st.session_state.pop("quote_hint", False):
        st.info(
            "Quotes and BOQs are created at sizing.dayliff.com after a lab report. "
            "The ticket below is the handoff — not the quote."
        )


def badge(kind: str, label: str) -> str:
    return f'<span class="badge badge-{kind}">{label}</span>'


def ai_pane(body: str, heading: str = "AI draft") -> None:
    safe = html.escape(body or "").replace("\n", "<br>")
    st.markdown(
        f'<div class="ai-pane"><div class="pane-label">{badge("ai", heading)}</div>{safe}</div>',
        unsafe_allow_html=True,
    )


def verified_pane(body: str, heading: str = "Approved") -> None:
    safe = html.escape(body or "").replace("\n", "<br>")
    st.markdown(
        f'<div class="ok-pane"><div class="pane-label">{badge("ok", heading)}</div>{safe}</div>',
        unsafe_allow_html=True,
    )


def origin_badge(status: str | None) -> str:
    if status == "approved":
        return badge("ok", "Verified")
    if status == "sent":
        return badge("ok", "Sent")
    if status == "rejected":
        return badge("medium", "Rejected")
    return badge("ai", "AI draft")


def confidence_legend(*, expanded: bool = False) -> None:
    with st.expander("What confidence and “Flag for rep” mean", expanded=expanded):
        st.markdown(
            with_glossary(
                "The crew scores how much it trusts its own brief. This is **not** a win-probability. "
                "It is a self-check: live Customer_Card vs demo fixtures, invoice coverage, "
                "and whether the buying committee was inferred."
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            """
| Score | What to do |
|---|---|
| **80%+** | Skim and approve if the facts match what you know of the site. |
| **50–79%** | Read the flags. Confirm plant age, contacts, or ERP number before sending. |
| **Below 50%** or **Flag for rep** | Treat as a hypothesis. Fix the facts in Site 360, then re-run prep. |
            """
        )


def value_strip(counts: dict) -> None:
    approved = int(counts.get("approved_drafts") or 0)
    minutes = approved * 45
    time_n = f"{minutes} min" if minutes < 120 else f"{minutes / 60:.0f} h"
    cards = [
        (
            counts.get("accounts", 0),
            "Accounts",
            "Customers this workspace can research — pipeline plus imported Customer_Card records.",
        ),
        (
            counts.get("pending_drafts", 0),
            "Drafts in queue",
            "AI-written email / LinkedIn waiting on a human. Nothing sends from this number.",
        ),
        (
            counts.get("alerts", 0),
            "Engineer alerts",
            "Installed-base plays: membrane windows, aging plant, rotting quotes, internal AR.",
        ),
        (
            counts.get("sizing_tickets", 0),
            "Sizing tickets",
            "Handoffs ready for a lab report in AI Product Sizing — still not a quote.",
        ),
        (
            approved,
            "Human-approved",
            "Drafts a rep marked SDR-ready. The trust line: AI drafts, humans release.",
        ),
        (
            time_n if approved else "~45 min",
            "Time returned",
            "45 min of Excel / WhatsApp research avoided per approved brief (conservative)."
            if approved
            else "Typical research time a brief replaces once a human approves it.",
        ),
    ]
    for row in (cards[:3], cards[3:]):
        cols = st.columns(3)
        for col, (n, lab, cap) in zip(cols, row):
            col.markdown(
                f'<div class="kpi"><div class="n">{n}</div><div class="l">{lab}</div>'
                f'<div class="c">{with_glossary(cap)}</div></div>',
                unsafe_allow_html=True,
            )


def walkthrough() -> None:
    force = bool(st.session_state.pop("show_guide", False))
    with st.expander("How this tool works — 60 seconds", expanded=force):
        st.markdown(
            with_glossary(
                "This tool watches your installed customer base, spots accounts to research or re-engage, "
                "drafts outreach for your approval, and once you have a lab report, hands off to "
                "AI Product Sizing for a real quote — quotes always live in sizing.dayliff.com, never here."
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            """
1. **Signal** — Alerts and Site 360 show who needs a conversation (service window, quiet plant, new logo).
2. **Prep** — The crew writes a brief and drafts. Treat them as AI drafts until you say otherwise.
3. **Human gate** — You edit and approve. Approval does **not** send.
4. **Size** — Take the ticket + lab PDF into sizing.dayliff.com.
5. **Quote** — Economy / Standard / Premium and the BOQ are created there, in Business Central.
            """
        )
        st.caption("Always available from **How this works ?** in the sidebar.")
    st.session_state["guide_seen"] = True


def insight_cards(items: Iterable[tuple[str, str, str, str]]) -> None:
    """items: (icon, title, caption, body)"""
    bundle = list(items)
    cols = st.columns(2)
    for i, (icon, title, caption, body) in enumerate(bundle):
        with cols[i % 2]:
            safe = html.escape(body or "—").replace("\n", "<br>")
            st.markdown(
                f'<div class="insight-card"><h4><span class="ico">{icon}</span>{title}</h4>'
                f'<div class="muted">{caption}</div><div style="margin-top:8px">{safe}</div></div>',
                unsafe_allow_html=True,
            )


def paginate(items: Sequence[T], *, key: str, page_size: int = 10) -> tuple[list[T], str]:
    total = len(items)
    pages = max(1, (total + page_size - 1) // page_size)
    sk = f"page_{key}"
    if sk not in st.session_state:
        st.session_state[sk] = 1
    page = int(st.session_state[sk])
    page = min(max(page, 1), pages)
    st.session_state[sk] = page
    c1, c2, c3, c4 = st.columns((1, 1, 2, 2))
    if c1.button("← Prev", key=f"{key}_prev", disabled=page <= 1):
        st.session_state[sk] = page - 1
        st.rerun()
    if c2.button("Next →", key=f"{key}_next", disabled=page >= pages):
        st.session_state[sk] = page + 1
        st.rerun()
    c3.caption(f"Page {page} of {pages}")
    c4.caption(f"{total} records · {page_size} / page")
    start = (page - 1) * page_size
    return (
        list(items[start : start + page_size]),
        f'<div class="pagebar">Showing {start + 1 if total else 0}–{min(start + page_size, total)} of {total}</div>',
    )


def stepper() -> None:
    """Back-compat alias — prefer pipeline_stepper(current_id)."""
    pipeline_stepper(None)
