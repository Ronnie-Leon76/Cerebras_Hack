from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    claim: str
    source: str
    confidence: float = Field(ge=0, le=1)


class ResearchBrief(BaseModel):
    firmographics: str
    technographics: str
    signals: list[str] = Field(default_factory=list)
    buying_committee: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.5)
    low_confidence_flags: list[str] = Field(default_factory=list)


class PainHypothesis(BaseModel):
    name: str
    fit: Literal["high", "medium", "low"]
    evidence: list[str] = Field(default_factory=list)
    recommended_angle: str
    use_case_id: str = ""


class ProductFit(BaseModel):
    item_no: str
    description: str
    family: str
    reason: str
    unit_price: float | None = None


class OutreachDraft(BaseModel):
    channel: Literal["email", "linkedin_note", "linkedin_followup"]
    subject: str = ""
    body: str
    personalization_vars: list[str] = Field(default_factory=list)
    status: Literal["pending_approval", "approved", "rejected", "sent"] = "pending_approval"


class HygienePlan(BaseModel):
    next_step: str
    follow_up_days: int = 5
    fields_to_update: dict[str, str] = Field(default_factory=dict)
    requires_rep_confirm: list[str] = Field(default_factory=list)


class SizingHandoff(BaseModel):
    """Ticket an engineer can paste into AI Product Sizing — not a quote."""

    technology: Literal["ro", "uf", "either"] = "ro"
    sizing_url: str = ""
    lab_reports_url: str = ""
    customers_url: str = ""
    lab_ask: list[str] = Field(default_factory=list)
    option_framing: str = (
        "Engineer runs Economy / Standard / Premium only after a lab report is in sizing."
    )
    do_not_quote: list[str] = Field(default_factory=list)
    customer_card: dict = Field(default_factory=dict)
    engineer_prompt: str = ""


class AccountPrepResult(BaseModel):
    account_id: str
    ran_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")
    research: ResearchBrief | None = None
    pains: list[PainHypothesis] = Field(default_factory=list)
    products: list[ProductFit] = Field(default_factory=list)
    drafts: list[OutreachDraft] = Field(default_factory=list)
    hygiene: HygienePlan | None = None
    sizing: SizingHandoff | None = None
    site: dict | None = None
    audit: list[str] = Field(default_factory=list)
    error: str | None = None
