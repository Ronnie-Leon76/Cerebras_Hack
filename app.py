from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src import bc, catalogue, config, crm, erp, hubspot, installed_base, knowledge, llm, notify
from src.graph import invoke_prep
from src.models import AccountPrepResult
from src.ui import inject, paginate, stepper

st.set_page_config(
    page_title="D&S Account Prep · Cerebras",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def hero() -> None:
    mode = "Cerebras live" if llm.has_llm() else "Demo mode"
    st.markdown(
        f"""
<div class="hero">
  <h1>Account Prep</h1>
  <p>Outbound intelligence for Davis &amp; Shirtliff. Search any ERP customer, see invoices and what we already installed, draft human-gated outreach, then hand a <b>sizing ticket</b> to AI Product Sizing. Agents notify engineers before plants go quiet.</p>
  <div class="pills">
    <span class="pill">{mode}</span>
    <span class="pill">{config.cerebras_model()}</span>
    <span class="pill">LangGraph crew</span>
    <span class="pill">CRM writes {'on' if config.allow_crm_write() else 'locked'}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def kpis() -> None:
    c = crm.counts()
    cols = st.columns(7)
    for col, (n, lab) in zip(
        cols,
        [
            (c["accounts"], "Accounts"),
            (c["pending_drafts"], "Drafts"),
            (c.get("alerts", 0), "Engineer alerts"),
            (c.get("sizing_tickets", 0), "Sizing tickets"),
            (c["approved_drafts"], "Approved"),
            (c["open_tasks"], "Tasks"),
            (c["stale"], "Stale"),
        ],
    ):
        col.markdown(
            f'<div class="kpi"><div class="n">{n}</div><div class="l">{lab}</div></div>',
            unsafe_allow_html=True,
        )


def sidebar() -> str:
    with st.sidebar:
        st.markdown("### D&S Account Prep")
        st.caption("Cafe Compute · Nairobi")
        nav = st.radio(
            "Workspace",
            [
                "Command",
                "Site 360",
                "Alerts",
                "Run prep",
                "Drafts",
                "Sizing tickets",
                "Catalogue",
                "Pitch",
                "Governance",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Drafts never send. Quotes live in sizing.dayliff.com.")
        if llm.has_llm():
            st.success("Cerebras connected")
        else:
            st.info("Demo mode — add CEREBRAS_API_KEY for live Qwen.")
    return nav


def page_command() -> None:
    hero()
    kpis()
    stepper()
    accounts = crm.list_accounts()
    stale = crm.stale_accounts()
    tickets = [a for a in accounts if a.get("sizing")]
    strategic = [a for a in accounts if a.get("strategic")]

    a, b, c = st.columns(3)
    with a:
        st.subheader("Needs attention")
        slice_, _ = paginate(stale, key="stale", page_size=4)
        for acc in slice_:
            st.markdown(
                f'<div class="acc-card"><h4>{acc["name"]}</h4>'
                f'<div class="muted">{acc.get("customer_no") or "—"} · {acc.get("city") or ""}, {acc.get("country") or ""} · '
                f'{"Strategic" if acc.get("strategic") else "Core"}</div>'
                f'<div class="muted">Last activity: {acc.get("last_activity_at") or "never"}</div></div>',
                unsafe_allow_html=True,
            )
    with b:
        st.subheader("Ready to size")
        if not tickets:
            st.caption("Run prep — a lab-ask ticket appears here.")
        else:
            slice_, _ = paginate(tickets, key="tickets_home", page_size=4)
            for acc in slice_:
                sz = acc.get("sizing") or {}
                tech = (sz.get("technology") or "ro").upper()
                st.markdown(
                    f'<div class="acc-card"><h4>{acc["name"]}</h4>'
                    f'<span class="badge badge-ro">{tech}</span>'
                    f'<div class="muted" style="margin-top:6px">Ask for a lab analysis, then open sizing.</div></div>',
                    unsafe_allow_html=True,
                )
    with c:
        st.subheader("Engineer alerts")
        alerts = crm.list_notifications(status="open")[:4]
        if not alerts:
            st.caption("Scan installed base from Alerts to notify engineers.")
        for n in alerts:
            st.markdown(
                f'<div class="acc-card"><h4>{n.get("title")}</h4>'
                f'<div class="muted">{n.get("severity")} · {n.get("account_name")} · {n.get("play")}</div></div>',
                unsafe_allow_html=True,
            )
        st.link_button("Open AI Product Sizing", config.sizing_base_url() + "/dashboard/water-treatment")
        st.caption("Strategic watch: " + ", ".join(x["name"] for x in strategic[:4]))


def page_accounts() -> None:
    st.header("Site 360")
    st.caption(
        "Search like sizing: Business Central Customer_Card (name / phone / customer no), then invoices, quotes, and what we already installed. "
        "Demo history is loaded if BC credentials are not in this environment."
    )
    q = st.text_input("Search customer", placeholder="Pharmakina, C-KE-11820, Ridgeview, +254…")
    country = st.selectbox(
        "BC company",
        ["KENYA", "UGANDA", "TANZANIA", "RWANDA", "ZAMBIA", "DRC"],
        index=0,
    )
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Search pipeline", type="primary"):
        st.session_state["local_hits"] = crm.search_accounts(q)
    if c2.button("Search Customer_Card", disabled=not bc.configured()):
        st.session_state["bc_hits"] = bc.search_customer_card(q, company=country)
        if not st.session_state["bc_hits"]:
            st.warning("No Customer_Card hits. Check BC_URL / credentials, or use pipeline search (demo cards).")
    if c3.button("Search microservice", disabled=not config.microservice_url()):
        st.session_state["erp_hits"] = erp.search_erp_customers(q, country=country)
    c4.caption("Customer_Card uses the same OData page as AI Product Sizing.")

    local = st.session_state.get("local_hits")
    if q and local is None:
        local = crm.search_accounts(q)
    if local:
        st.subheader("Pipeline")
        page_l, html = paginate(local, key="local360", page_size=6)
        st.markdown(html, unsafe_allow_html=True)
        for r in page_l:
            cols = st.columns((4, 1))
            cols[0].markdown(
                f"**{r['name']}** · `{r.get('customer_no') or '—'}` · {r.get('city') or ''}, {r.get('country') or ''}"
            )
            if cols[1].button("Open 360", key=f"o-{r['id']}"):
                st.session_state["focus_account"] = r["id"]
                st.rerun()

    bc_hits = st.session_state.get("bc_hits") or []
    if bc_hits:
        st.subheader("Business Central Customer_Card")
        page_b, _ = paginate(bc_hits, key="bccard", page_size=8)
        st.dataframe(page_b, use_container_width=True, hide_index=True)
        pick = st.selectbox(
            "Import + open",
            [f"{h.get('customer_no')} · {h.get('name')}" for h in page_b],
        )
        if st.button("Save card and open 360") and pick:
            row = page_b[[f"{h.get('customer_no')} · {h.get('name')}" for h in page_b].index(pick)]
            existing = crm.get_account_by_customer_no(str(row.get("customer_no") or ""))
            aid = (existing or {}).get("id") or ""
            aid = crm.upsert_account(
                {
                    "id": aid or None,
                    "name": row.get("name"),
                    "customer_no": row.get("customer_no"),
                    "phone": row.get("phone"),
                    "email": row.get("email"),
                    "city": row.get("city"),
                    "country": row.get("country") or country.title(),
                    "type": "INDUSTRIAL",
                    "segment": "industrial",
                    "notes": f"Imported from Customer_Card {row.get('salesperson_code') or ''}",
                }
            )
            st.session_state["focus_account"] = aid
            st.rerun()

    hits = st.session_state.get("erp_hits") or []
    if hits:
        st.subheader("Microservice ERP")
        page_hits, _ = paginate(hits, key="erp", page_size=8)
        st.dataframe(page_hits, use_container_width=True, hide_index=True)

    with st.expander("Add a card manually"):
        with st.form("new_account"):
            a, b, c = st.columns(3)
            name = a.text_input("Name")
            customer_no = b.text_input("Customer no")
            domain = c.text_input("Domain")
            a2, b2, c2 = st.columns(3)
            city = a2.text_input("City")
            country_f = b2.selectbox("Country", knowledge.icp().get("regions") or ["Kenya"])
            typ = c2.selectbox(
                "Type",
                ["INDUSTRIAL", "COMMERCIAL", "MUNICIPAL", "INSTITUTIONAL", "RESIDENTIAL", "NGO"],
            )
            segs = [s["id"] for s in knowledge.icp().get("segments") or []]
            segment = st.selectbox("ICP segment", segs)
            persona_name = st.text_input("Champion name")
            persona_title = st.text_input("Champion title")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            notes = st.text_area("Trigger / notes")
            strategic = st.checkbox("Strategic (always human-approve)")
            if st.form_submit_button("Save card") and name.strip():
                aid = crm.upsert_account(
                    {
                        "name": name.strip(),
                        "customer_no": customer_no,
                        "domain": domain,
                        "city": city,
                        "country": country_f,
                        "type": typ,
                        "segment": segment,
                        "persona_name": persona_name,
                        "persona_title": persona_title,
                        "email": email,
                        "phone": phone,
                        "notes": notes,
                        "strategic": strategic,
                        "signals": [t.strip() for t in notes.replace(",", " ").split() if len(t.strip()) > 3][:8],
                    }
                )
                st.session_state["focus_account"] = aid
                st.rerun()

    focus = st.session_state.get("focus_account")
    if focus:
        acc = crm.get_account(focus)
        if acc:
            _render_360(acc)
    elif not q:
        st.info("Try **Pharmakina** or **C-KE-11820** (Ridgeview) to see invoices + installed plant.")


def _render_360(account: dict) -> None:
    site = installed_base.load_site_360(account)
    card = site.get("card") or {}
    st.markdown(f"### {account.get('name')} · `{account.get('customer_no') or 'no ERP no'}`")
    src = "Live Customer_Card" if site.get("live_bc") else card.get("source") or "local history"
    st.caption(f"Source: {src} · engineer {site.get('engineer') or '—'}")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Balance", f"{float(card.get('balance') or 0):,.0f}")
    k2.metric("Credit limit", f"{float(card.get('credit_limit') or 0):,.0f}")
    k3.metric("Installed assets", len(site.get("installed_base") or []))
    k4.metric("Open plays", len(site.get("plays") or []))
    t_card, t_inst, t_inv, t_q, t_time, t_play = st.tabs(
        ["Card", "Installed", "Invoices", "Quotes", "Timeline", "Plays"]
    )
    with t_card:
        st.json(
            {
                k: card.get(k)
                for k in (
                    "customer_no",
                    "name",
                    "phone",
                    "email",
                    "address",
                    "city",
                    "country",
                    "price_group",
                    "salesperson_code",
                    "responsibility_center",
                    "blocked",
                    "type",
                )
            }
        )
        if st.button("Run prep on this account", type="primary"):
            st.session_state["prep_account_id"] = account["id"]
            st.info("Switch to **Run prep** — this account will be pre-selected if you pick it in the dropdown.")
    with t_inst:
        rows = site.get("installed_base") or []
        if not rows:
            st.write("No installed-base rows. Treat as new logo until BC history loads.")
        else:
            page, html = paginate(rows, key="inst", page_size=8)
            st.markdown(html, unsafe_allow_html=True)
            st.dataframe(page, use_container_width=True, hide_index=True)
    with t_inv:
        rows = site.get("invoices") or []
        if not rows:
            st.write("No posted invoices on file.")
        else:
            page, html = paginate(rows, key="inv", page_size=8)
            st.markdown(html, unsafe_allow_html=True)
            st.dataframe(page, use_container_width=True, hide_index=True)
    with t_q:
        rows = site.get("quotes") or []
        st.dataframe(rows, use_container_width=True, hide_index=True) if rows else st.write("No open quotes.")
    with t_time:
        acts = crm.list_activities(account["id"])
        page, html = paginate(acts, key="tl", page_size=10)
        st.markdown(html, unsafe_allow_html=True)
        st.dataframe(page, use_container_width=True, hide_index=True)
        st.write(account.get("notes") or "")
    with t_play:
        plays = site.get("plays") or []
        if st.button("Notify engineer (create alerts + tasks)"):
            n = installed_base.persist_notifications(
                account["id"], site.get("engineer") or account.get("persona_name") or "engineer", plays
            )
            st.success(f"{n} new alerts.")
            st.rerun()
        for p in plays:
            st.markdown(
                f'<span class="badge badge-{"high" if p.get("severity")=="high" else "medium"}">{p.get("severity")}</span> **{p.get("title")}**',
                unsafe_allow_html=True,
            )
            st.caption(p.get("body"))
            if st.button("Email this play", key=f"em-{account['id']}-{p.get('play')}-{p.get('title','')[:12]}"):
                res = notify.send_play_email(p, account.get("name") or "")
                st.write(res)


def _render_sizing(sz, key: str = "sz") -> None:
    if not sz:
        return
    data = sz.model_dump() if hasattr(sz, "model_dump") else sz
    st.markdown("#### Sizing ticket")
    t1, t2 = st.columns((1, 3))
    t1.markdown(f'<span class="badge badge-ro">{data.get("technology","ro").upper()}</span>', unsafe_allow_html=True)
    t2.caption(data.get("option_framing") or "")
    st.markdown("**Lab ask (engineer / customer)**")
    st.write(" · ".join(data.get("lab_ask") or []))
    st.code(data.get("engineer_prompt") or "", language=None)
    b1, b2, b3 = st.columns(3)
    if data.get("sizing_url"):
        b1.link_button("Open RO/UF bench", data["sizing_url"])
    if data.get("lab_reports_url"):
        b2.link_button("Lab reports", data["lab_reports_url"])
    if data.get("customers_url"):
        b3.link_button("Customer cards in sizing", data["customers_url"])
    st.download_button(
        "Download customer card JSON",
        json.dumps(data.get("customer_card") or {}, indent=2),
        file_name=f"customer-card-{key}.json",
        mime="application/json",
        key=f"card-{key}",
    )


def _render_result(result: AccountPrepResult, account: dict) -> None:
    st.success(f"Prep complete for {account.get('name')} · {result.ran_at}")
    if result.research:
        r = result.research
        st.markdown("#### Research")
        m1, m2 = st.columns(2)
        m1.markdown(f"**Firmographics**  \n{r.firmographics}")
        m2.markdown(f"**Technographics**  \n{r.technographics}")
        st.markdown("**Buying committee:** " + ", ".join(r.buying_committee or ["—"]))
        st.markdown("**Signals:** " + ", ".join(r.signals or ["—"]))
        st.caption(f"Confidence {r.confidence:.0%}")
        if r.low_confidence_flags:
            st.warning("Flag for rep: " + "; ".join(r.low_confidence_flags))
        if r.evidence:
            ev, _ = paginate(r.evidence, key="ev", page_size=5)
            st.dataframe([e.model_dump() for e in ev], use_container_width=True, hide_index=True)
    if result.pains:
        st.markdown("#### Pains & use-cases")
        for p in result.pains:
            st.markdown(
                f'<span class="badge badge-{p.fit}">{p.fit} fit</span> **{p.name}**',
                unsafe_allow_html=True,
            )
            st.caption(p.recommended_angle)
            if p.evidence:
                st.write("Evidence: " + " · ".join(p.evidence))
    if result.products:
        st.markdown("#### Hypothesized catalogue (internal)")
        st.caption("Shown to the SDR as a starting family — the BOQ is created in sizing after the lab.")
        st.dataframe(
            [{k: v for k, v in p.model_dump().items() if k != "unit_price"} for p in result.products],
            use_container_width=True,
            hide_index=True,
        )
    _render_sizing(result.sizing, result.account_id)
    if result.site:
        st.markdown("#### Site 360 snapshot")
        st.write(
            f"Installed assets: {result.site.get('installed_count')} · "
            f"Invoices: {result.site.get('invoice_count')} · "
            f"Open quotes: {result.site.get('quote_count')} · "
            f"Balance: {result.site.get('balance')}"
        )
        for p in (result.site.get("plays") or [])[:4]:
            st.caption(f"{p.get('severity')}: {p.get('title')}")
    if result.drafts:
        st.markdown("#### Outreach queued for approval")
        for d in result.drafts:
            st.markdown(f"**{d.channel}** · {d.subject or '—'}")
            st.markdown(f'<div class="draft-box">{d.body}</div>', unsafe_allow_html=True)
    if result.hygiene:
        st.markdown("#### Hygiene")
        st.write(result.hygiene.next_step)
        st.caption("Requires rep confirm: " + ", ".join(result.hygiene.requires_rep_confirm))
    with st.expander("Audit trail"):
        st.write(result.audit)


def page_run() -> None:
    st.header("Run account prep")
    stepper()
    accounts = crm.list_accounts()
    labels = {f"{a['name']} ({a.get('customer_no') or a['id']})": a["id"] for a in accounts}
    keys = list(labels.keys())
    if not keys:
        st.warning("Add an account in Site 360 first.")
        return
    idx = 0
    pref = st.session_state.get("prep_account_id")
    if pref:
        for i, aid in enumerate(labels.values()):
            if aid == pref:
                idx = i
                break
    choice = st.selectbox("Account", keys, index=idx if keys else 0)
    account = crm.get_account(labels[choice]) if choice else None
    if account:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Segment", account.get("segment") or "—")
        c2.metric("Site", f"{account.get('city') or '—'}, {account.get('country') or '—'}")
        c3.metric("Strategic", "Yes" if account.get("strategic") else "No")
        c4.metric("ERP no", account.get("customer_no") or "—")
        st.info(account.get("notes") or "No notes")

    go = st.button("Run LangGraph crew", type="primary", disabled=not account)
    if go and account:
        with st.spinner("Research → pains → catalogue → drafts → sizing ticket…"):
            result = invoke_prep(account)
        st.session_state["last_prep"] = result.model_dump()
        st.session_state["last_account"] = account
        if config.allow_crm_write() and hubspot.enabled() and result.research:
            hubspot.upsert_note(
                "",
                f"Account Prep {result.ran_at}\n{result.research.firmographics}",
            )

    if st.session_state.get("last_prep"):
        res = AccountPrepResult.model_validate(st.session_state["last_prep"])
        acc = st.session_state.get("last_account") or account or {}
        _render_result(res, acc)


def page_drafts() -> None:
    st.header("Human-in-the-loop drafts")
    st.caption("Edit tone if needed. Approve does not send — it marks the copy as SDR-ready.")
    status = st.radio("Queue", ["pending_approval", "approved", "rejected"], horizontal=True)
    drafts = crm.list_drafts(status=status)
    if not drafts:
        st.info("Empty queue. Run prep on an account.")
        return
    page, html = paginate(drafts, key=f"drafts_{status}", page_size=4)
    st.markdown(html, unsafe_allow_html=True)
    for d in page:
        with st.container(border=True):
            st.markdown(
                f"**{d.get('account_name') or d.get('account_id')}** · `{d.get('channel')}`"
            )
            subject = st.text_input("Subject", d.get("subject") or "", key=f"sub-{d['id']}")
            body = st.text_area("Body", d.get("body") or "", height=160, key=f"body-{d['id']}")
            a, b, c, e = st.columns(4)
            if a.button("Save edit", key=f"sv-{d['id']}"):
                crm.update_draft_body(d["id"], subject, body)
                st.toast("Saved")
            if b.button("Approve", key=f"ok-{d['id']}"):
                crm.update_draft_body(d["id"], subject, body)
                crm.decide_draft(d["id"], "approved", "sdr")
                crm.add_activity(d["account_id"], "draft_approved", d.get("channel") or "")
                st.rerun()
            if c.button("Reject", key=f"no-{d['id']}"):
                crm.decide_draft(d["id"], "rejected", "sdr")
                st.rerun()
            if e.button("Log activity", key=f"log-{d['id']}"):
                crm.add_activity(d["account_id"], "logged", "manual")
                st.toast("Logged locally")


def page_tickets() -> None:
    st.header("Sizing tickets")
    st.caption("Handoff packets for the engineer. Lab PDF still has to be uploaded in AI Product Sizing.")
    accounts = [a for a in crm.list_accounts() if a.get("sizing")]
    if not accounts:
        st.info("No tickets yet. Run prep — every brief now emits a sizing ticket.")
        return
    page, html = paginate(accounts, key="all_tickets", page_size=5)
    st.markdown(html, unsafe_allow_html=True)
    for acc in page:
        st.markdown(f"### {acc['name']}")
        _render_sizing(acc.get("sizing"), acc["id"])
        st.divider()


def page_catalogue() -> None:
    st.header("Dayliff catalogue")
    st.caption("Curated extract the mapper uses. Same families as water-treatment recommendations — not the live quote.")
    fams = catalogue.families()
    counts = {f: sum(1 for r in catalogue.load_catalogue() if r.get("family") == f) for f in fams}
    fam = st.selectbox("Family", ["all"] + [f"{f} ({counts[f]})" for f in fams])
    q = st.text_input("SKU or description", placeholder="DRO, BRO, PXD, chlorine, UV…")
    size = st.selectbox("Rows per page", [10, 20, 40, 80], index=1)
    family = None if fam == "all" else fam.split(" (")[0]
    rows = catalogue.filter_catalogue(q, family=family)
    page, html = paginate(rows, key=f"cat_{family}_{q}", page_size=int(size))
    st.markdown(html, unsafe_allow_html=True)
    view = [
        {
            "item_no": r.get("item_no"),
            "description": r.get("description"),
            "family": r.get("family"),
        }
        for r in page
    ]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.caption(f"{len(catalogue.load_catalogue())} SKUs in extract · prices hidden from this SDR view")


def page_gov() -> None:
    st.header("Governance")
    st.markdown(
        f"""
| Control | Value |
|---|---|
| Cerebras model | `{config.cerebras_model()}` |
| Sizing | `{config.sizing_base_url()}` |
| CRM write (HubSpot notes) | `{'allowed' if config.allow_crm_write() else 'denied'}` |
| Auto-approve non-strategic | `{config.auto_approve_nonstrategic()}` |
| HubSpot | `{'present' if hubspot.enabled() else 'not set'}` |
| ERP microservice | `{config.microservice_url() or 'not set'}` |
| BC Customer_Card | `{'live' if bc.configured() else 'fixture / demo'}` |
| Engineer notify email | `{config.notify_engineer_email() or 'in-app only'}` |
        """
    )
    st.markdown(
        "**Write policy.** Local activity, tasks, alerts, and drafts: allowed. HubSpot notes: opt-in. "
        "Outbound email/LinkedIn still needs human approval. Deal stage / forecast: rep only. "
        "Quotes and BOQs: AI Product Sizing only. Invoice amounts stay internal — never in customer drafts."
    )
    logs = crm.list_audit(200)
    page, html = paginate(logs, key="audit", page_size=15)
    st.markdown(html, unsafe_allow_html=True)
    st.dataframe(page, use_container_width=True, hide_index=True)
    st.download_button(
        "Export accounts JSON",
        json.dumps(crm.list_accounts(), indent=2, default=str),
        file_name="dns-accounts.json",
        mime="application/json",
    )


def page_alerts() -> None:
    st.header("Proactive engineer alerts")
    st.caption(
        "The crew scans installed plant age, open AR, rotting quotes, and aftermarket windows — then notifies the sales engineer. "
        "Customer-facing drafts never mention overdue invoices."
    )
    a, b = st.columns(2)
    if a.button("Scan all installed-base accounts", type="primary"):
        with st.spinner("Reading Customer_Card history + fixtures…"):
            summary = installed_base.scan_all_accounts()
        st.success(f"Scanned {summary['scanned']} accounts · {summary['alerts_created']} new alerts")
        st.rerun()
    status = b.radio("Queue", ["open", "done"], horizontal=True)
    notes = crm.list_notifications(status=status)
    if not notes:
        st.info("No alerts yet. Scan the installed base or run prep on Pharmakina / Ridgeview.")
        return
    page, html = paginate(notes, key=f"al_{status}", page_size=6)
    st.markdown(html, unsafe_allow_html=True)
    for n in page:
        with st.container(border=True):
            st.markdown(f"**{n.get('title')}**")
            st.caption(
                f"{n.get('severity')} · {n.get('play')} · {n.get('account_name')} `{n.get('customer_no') or ''}` · {n.get('engineer')}"
            )
            st.write(n.get("body"))
            x, y, z = st.columns(3)
            if x.button("Open 360", key=f"z-{n['id']}"):
                st.session_state["focus_account"] = n.get("account_id")
                st.info("Open **Site 360** in the sidebar.")
            if y.button("Notify by email", key=f"n-{n['id']}"):
                st.write(
                    notify.send_play_email(
                        {
                            "title": n.get("title"),
                            "body": n.get("body"),
                            "play": n.get("play"),
                            "severity": n.get("severity"),
                        },
                        n.get("account_name") or "",
                    )
                )
            if z.button("Mark done", key=f"d-{n['id']}"):
                crm.close_notification(n["id"])
                st.rerun()


def page_pitch() -> None:
    st.header("Cafe Compute pitch (8 minutes)")
    st.markdown(
        """
**One line.** D&S already knows the water. This agent remembers the *customer* — what we installed, what they still owe, what is due for service — and puts a sizing ticket in the engineer’s hand before the plant goes quiet.

### Clock
1. **0:00 Problem** — SDRs research in WhatsApp and Excel. Installed sites get a cold “new RO” email. Aftermarket revenue sleeps until the customer shouts.
2. **0:45 Show Command** — KPIs, pipeline, alerts. “This is not a chatbot. It is a crew with gates.”
3. **1:30 Site 360** — Search **Pharmakina**. Card, 2019 DRO, invoices, open AR, PW expansion quote. “Same Customer_Card the sizing app uses.”
4. **3:00 Run prep** — LangGraph on Cerebras. Drafts talk *service*, not greenfield. Sizing ticket: Ph. Eur. lab ask, ERP customer no, no prices.
5. **4:30 Alerts** — Scan installed base. Membrane window on Pharmakina, ageing Nakuru plant, Ridgeview chlorine. Click notify.
6. **6:00 Tandem** — Open sizing.dayliff.com. “Lab PDF → Economy / Standard / Premium → BC quote. This app never quotes.”
7. **7:00 Value** — Close with the numbers below. Ask for a 30-day SDR pilot, draft-only.

### Business value (say out loud)
| Lever | What changes | Conservative year-1 picture |
|---|---|---|
| Prep time | 45–90 min of research → ~8 min review | 6 SDRs × 6 hrs/week × 48 weeks |
| Aftermarket | Membrane / media / UV plays on installed plants | One extra spares job per engineer per month |
| Quote quality | No recycled 2019 prices; lab-first sizing | Fewer giveaways and fewer “wrong plant” FATs |
| Collections | AR visible before a new BOQ | Credit control in the same screen as the chase |
| Meetings | Personalized, evidence-backed outreach | Higher reply rate vs spray-and-pray |

**Pilot ask.** 1 country, 1 salesperson code, draft-only for 4 weeks. Measure: acceptance rate of drafts, alerts acted on, lab reports into sizing, quotes created on agent-prepped accounts.

**What we will not claim.** We do not auto-send email. We do not invent invoices when BC is offline (fixtures are labelled). We do not replace the engineer.
        """
    )


def main() -> None:
    inject()
    nav = sidebar()
    pages = {
        "Command": page_command,
        "Site 360": page_accounts,
        "Alerts": page_alerts,
        "Run prep": page_run,
        "Drafts": page_drafts,
        "Sizing tickets": page_tickets,
        "Catalogue": page_catalogue,
        "Pitch": page_pitch,
        "Governance": page_gov,
    }
    pages[nav]()


main()
