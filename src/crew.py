from __future__ import annotations

import json

from . import catalogue, crm, installed_base, knowledge, llm
from .models import (
    AccountPrepResult,
    Evidence,
    HygienePlan,
    OutreachDraft,
    PainHypothesis,
    ProductFit,
    ResearchBrief,
)


def run_account_prep(account: dict) -> AccountPrepResult:
    result = AccountPrepResult(account_id=account["id"])
    audit: list[str] = []

    site = installed_base.load_site_360(account)
    result.site = {
        "card": site.get("card"),
        "installed_count": len(site.get("installed_base") or []),
        "invoice_count": len(site.get("invoices") or []),
        "quote_count": len(site.get("quotes") or []),
        "plays": site.get("plays") or [],
        "live_bc": site.get("live_bc"),
        "balance": (site.get("card") or {}).get("balance"),
    }
    n = installed_base.persist_notifications(
        account["id"], site.get("engineer") or account.get("persona_name") or "engineer", site.get("plays") or []
    )
    audit.append(f"site 360: {result.site['installed_count']} assets, {result.site['invoice_count']} invoices, {n} new alerts")
    if site.get("installed_base"):
        account = {
            **account,
            "notes": (account.get("notes") or "")
            + " | installed: "
            + ", ".join(str(x.get("item_no") or x.get("description")) for x in site["installed_base"][:4]),
            "signals": list(account.get("signals") or []) + ["installed base", "aftermarket"],
        }

    use_cases = knowledge.match_use_cases(account)
    audit.append(f"matched {len(use_cases)} use-case patterns")

    hits = knowledge.web_research(account.get("name") or "", account.get("domain"))
    audit.append(f"web hits={len(hits)}")

    families = []
    for uc in use_cases:
        fam = uc.get("lead_family") or uc.get("catalogue_families") or uc.get("families")
        if isinstance(fam, list):
            families.extend(fam)
        elif fam:
            families.append(fam)
    q = " ".join(account.get("signals") or []) or account.get("segment") or "RO"
    products = catalogue.search_catalogue(q, limit=6)
    if families:
        extra = []
        for fam in dict.fromkeys(families):
            extra.extend(catalogue.search_catalogue(q, family=fam, limit=3))
        seen = {p.get("item_no") for p in products}
        for p in extra:
            if p.get("item_no") not in seen:
                products.append(p)
                seen.add(p.get("item_no"))
        products = products[:8]

    result.products = [
        ProductFit(
            item_no=str(p.get("item_no") or ""),
            description=str(p.get("description") or ""),
            family=str(p.get("family") or ""),
            reason="Matched ICP / account signals against D&S catalogue",
            unit_price=p.get("unit_price"),
        )
        for p in products
    ]

    if llm.has_llm():
        try:
            result.research = _research_llm(account, hits, use_cases)
            audit.append("research: cerebras")
        except Exception as exc:
            result.research = _research_fallback(account, hits)
            audit.append(f"research fallback: {exc}")
        try:
            result.pains = _pains_llm(account, use_cases, result.products)
            audit.append("pains: cerebras")
        except Exception as exc:
            result.pains = _pains_fallback(use_cases)
            audit.append(f"pains fallback: {exc}")
        try:
            result.drafts = _drafts_llm(account, result)
            audit.append("drafts: cerebras")
        except Exception as exc:
            result.drafts = _drafts_fallback(account, result)
            audit.append(f"drafts fallback: {exc}")
    else:
        result.research = _research_fallback(account, hits)
        result.pains = _pains_fallback(use_cases)
        result.drafts = _drafts_fallback(account, result)
        audit.append("demo mode (no CEREBRAS_API_KEY)")

    result.sizing = knowledge.build_sizing_handoff(account, use_cases, result.products)
    audit.append(f"sizing ticket: {result.sizing.technology}")

    result.hygiene = HygienePlan(
        next_step="Rep approves drafts, then collects a lab report so engineering can size Economy/Standard/Premium",
        follow_up_days=5 if not account.get("strategic") else 3,
        fields_to_update={
            "last_activity_at": "prep_run",
            "champion_identified": account.get("persona_title") or "",
        },
        requires_rep_confirm=["deal_stage", "forecast"],
    )
    result.audit = audit
    crm.add_activity(account["id"], "account_prep", json.dumps(audit))
    crm.log_audit(account["id"], "crew", "account_prep_complete", audit)
    crm.save_drafts(account["id"], [d.model_dump() for d in result.drafts])
    crm.add_task(
        account["id"],
        f"Review prep + drafts for {account.get('name')}",
        result.hygiene.follow_up_days,
    )
    crm.save_last_prep(account["id"], result.model_dump())
    crm.add_task(
        account["id"],
        f"Collect lab report → size in {result.sizing.technology.upper() if result.sizing else 'RO'}",
        7,
    )
    return result


def _research_llm(account: dict, hits: list[dict], use_cases: list[dict]) -> ResearchBrief:
    payload = llm.complete_json(
        f"""Build a structured account research brief for Davis & Shirtliff (water, energy, pumps, treatment).
Account JSON:
{json.dumps(account, default=str)}
Web snippets:
{json.dumps(hits[:5], default=str)}
Matched use cases:
{json.dumps(use_cases, default=str)}

Return JSON with keys:
firmographics (string), technographics (string), signals (string[]),
buying_committee (string[] of likely roles), evidence (array of {{claim, source, confidence 0-1}}),
confidence (0-1), low_confidence_flags (string[]).
Never invent funding rounds or customer names not in the inputs; flag them instead.
"""
    )
    ev = [Evidence(**e) if isinstance(e, dict) else Evidence(claim=str(e), source="model", confidence=0.4)
          for e in payload.get("evidence") or []]
    return ResearchBrief(
        firmographics=str(payload.get("firmographics") or ""),
        technographics=str(payload.get("technographics") or ""),
        signals=list(payload.get("signals") or []),
        buying_committee=list(payload.get("buying_committee") or []),
        evidence=ev,
        confidence=float(payload.get("confidence") or 0.55),
        low_confidence_flags=list(payload.get("low_confidence_flags") or []),
    )


def _research_fallback(account: dict, hits: list[dict]) -> ResearchBrief:
    evidence = [
        Evidence(
            claim=h.get("title") or "web snippet",
            source=h.get("href") or "web",
            confidence=0.45,
        )
        for h in hits[:4]
    ]
    if not evidence:
        evidence = [
            Evidence(
                claim=account.get("notes") or "Internal CRM notes only",
                source="crm",
                confidence=0.7,
            )
        ]
    return ResearchBrief(
        firmographics=(
            f"{account.get('name')} · {account.get('city') or ''}, {account.get('country') or ''} · "
            f"{account.get('type') or ''} / {account.get('segment') or ''}"
        ),
        technographics="Inferred from notes and D&S catalogue fit; live stack not confirmed.",
        signals=list(account.get("signals") or []),
        buying_committee=[
            account.get("persona_title") or "Engineering",
            "Procurement",
            "Operations / plant",
        ],
        evidence=evidence,
        confidence=0.58 if hits else 0.72,
        low_confidence_flags=[] if account.get("notes") else ["thin public footprint"],
    )


def _pains_llm(account: dict, use_cases: list[dict], products: list[ProductFit]) -> list[PainHypothesis]:
    payload = llm.complete_json(
        f"""Map pains and use-cases for this D&S account.
Account: {json.dumps(account, default=str)}
Use cases: {json.dumps(use_cases, default=str)}
Catalogue fits: {json.dumps([p.model_dump() for p in products], default=str)}

Return JSON {{ "pains": [ {{ "name", "fit": high|medium|low, "evidence": string[], "recommended_angle", "use_case_id" }} ] }}
Max 3 pains. Evidence must be grounded in the account notes/signals.
"""
    )
    out = []
    for p in payload.get("pains") or []:
        fit = str(p.get("fit") or "medium").lower()
        if fit not in {"high", "medium", "low"}:
            fit = "medium"
        out.append(
            PainHypothesis(
                name=str(p.get("name") or "Unnamed"),
                fit=fit,  # type: ignore[arg-type]
                evidence=list(p.get("evidence") or []),
                recommended_angle=str(p.get("recommended_angle") or ""),
                use_case_id=str(p.get("use_case_id") or ""),
            )
        )
    return out[:3] or _pains_fallback(use_cases)


def _pains_fallback(use_cases: list[dict]) -> list[PainHypothesis]:
    if not use_cases:
        return [
            PainHypothesis(
                name="Unspecified water reliability",
                fit="medium",
                evidence=["No strong pattern match yet"],
                recommended_angle="Lead with site survey + water analysis",
                use_case_id="",
            )
        ]
    pains = []
    for uc in use_cases[:3]:
        fit = "high" if uc.get("score", 0) >= 3 else "medium"
        pains.append(
            PainHypothesis(
                name=str(uc.get("name") or uc.get("id") or "Use case"),
                fit=fit,  # type: ignore[arg-type]
                evidence=list(uc.get("matched") or []) or [str(uc.get("id"))],
                recommended_angle=str(uc.get("angle") or uc.get("recommended_angle") or uc.get("description") or ""),
                use_case_id=str(uc.get("id") or ""),
            )
        )
    return pains


def _drafts_llm(account: dict, result: AccountPrepResult) -> list[OutreachDraft]:
    claims = knowledge.claims()
    site_note = json.dumps(result.site or {}, default=str)[:2000]
    payload = llm.complete_json(
        f"""Draft outbound for a D&S SDR. Human will approve before send. Never invent prices.
If site history shows installed Dayliff equipment, this is aftermarket / expansion — reference the existing plant, not a cold sale.
Never mention invoice amounts or overdue AR in customer-facing copy.
Voice:
{knowledge.voice()[:1800]}
Approved claims: {json.dumps(claims.get('approved') or claims, default=str)[:2500]}
Account: {json.dumps(account, default=str)}
Site 360: {site_note}
Research: {result.research.model_dump() if result.research else {}}
Pains: {[p.model_dump() for p in result.pains]}
Products (SKU only, no prices in copy unless from claims): {[p.item_no + ' ' + p.description for p in result.products[:4]]}

Return JSON:
{{
  "drafts": [
    {{"channel":"email","subject":"","body":"","personalization_vars":[]}},
    {{"channel":"email","subject":"","body":"","personalization_vars":[]}},
    {{"channel":"linkedin_note","subject":"","body":"","personalization_vars":[]}},
    {{"channel":"linkedin_followup","subject":"","body":"","personalization_vars":[]}}
  ]
}}
Emails: 80-130 words. CTA must be a water analysis / site visit so engineering can run AI Product Sizing (Economy/Standard/Premium). Never quote prices. LinkedIn note <280 chars.
"""
    )
    drafts = []
    for d in payload.get("drafts") or []:
        ch = str(d.get("channel") or "email")
        if ch not in {"email", "linkedin_note", "linkedin_followup"}:
            ch = "email"
        drafts.append(
            OutreachDraft(
                channel=ch,  # type: ignore[arg-type]
                subject=str(d.get("subject") or ""),
                body=str(d.get("body") or ""),
                personalization_vars=list(d.get("personalization_vars") or []),
            )
        )
    return drafts[:4] or _drafts_fallback(account, result)


def _drafts_fallback(account: dict, result: AccountPrepResult) -> list[OutreachDraft]:
    name = account.get("persona_name") or "there"
    company = account.get("name") or "your site"
    angle = result.pains[0].recommended_angle if result.pains else "reliable water & energy on site"
    sku = result.products[0].item_no if result.products else "a packaged treatment train"
    installed = bool(result.site and result.site.get("installed_count"))
    opener = (
        f"I looked after the Dayliff equipment already on {company}'s site and wanted to check in on uptime and the next service window."
        if installed
        else f"I support Davis & Shirtliff accounts in {account.get('country') or 'East Africa'} "
        f"and noticed {company} is looking at {', '.join((account.get('signals') or ['water quality'])[:2])}."
    )
    email1 = (
        f"Hi {name},\n\n{opener}\n\n{angle}\n\n"
        f"If you share a current water analysis we will run Economy / Standard / Premium in our sizing tool "
        f"(reference family {sku}) — no price until engineering sees the water.\n\n"
        f"Would a 20-minute call this week work?\n\nKind regards"
    )
    email2 = (
        f"Hi {name},\n\nShort note from D&S. "
        + (
            f"Because we already have a plant history with {company}, the fastest win is usually spares, membranes, or a capacity add-on — not a greenfield quote. "
            if installed
            else f"If {company} is still wrestling with {(account.get('signals') or ['uptime'])[0]}, we can bring a local engineer plus spares coverage. "
        )
        + "No pricing until we see the water.\n\nOpen to a site visit?\n\nKind regards"
    )
    note = (
        f"Hi {name} — D&S water/energy in {account.get('city') or account.get('country') or 'the region'}. "
        f"Saw {company}'s work on {(account.get('signals') or ['operations'])[0]}. "
        f"May I share a short site-prep note?"
    )
    follow = (
        f"Following up, {name}. If helpful I can send a one-page brief mapping likely treatment steps "
        f"for {company} — still subject to water analysis. Worth 10 minutes?"
    )
    return [
        OutreachDraft(channel="email", subject=f"{company}: water & energy site prep", body=email1, personalization_vars=["signals", "sku"]),
        OutreachDraft(channel="email", subject=f"Local support for {company}", body=email2, personalization_vars=["country"]),
        OutreachDraft(channel="linkedin_note", body=note, personalization_vars=["city"]),
        OutreachDraft(channel="linkedin_followup", body=follow, personalization_vars=["company"]),
    ]
