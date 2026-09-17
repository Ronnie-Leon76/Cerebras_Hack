# D&S Account Prep

Streamlit CRM workspace for Davis & Shirtliff outbound SDRs. A LangGraph crew (research → ICP / pain mapping → catalogue fit → outreach drafts → hygiene) runs on **Cerebras Inference** (`qwen-3.8-27b`). It sits **next to** [AI Product Sizing](https://sizing.dayliff.com) — it does not live in that UI. Quotes and BOQs still happen in sizing after a lab report.

Handoff: every prep run writes a **sizing ticket** (RO vs UF, lab-ask list, ERP customer card JSON, deep links into `sizing.dayliff.com`). Quotes, Economy/Standard/Premium options, BOQ and proposals stay in the sizing tool.

## What it does

1. **Site 360** — search the pipeline or live BC `Customer_Card` (same OData as sizing). Invoices, quotes, installed plant, AR.
2. **Alerts** — scan installed base; notify sales engineers (in-app + optional email). Membrane / media / UV / collections / rotting quotes.
3. **Prep crew** — research, ICP, drafts (aftermarket-aware), sizing ticket.
4. Human approval queue. Catalogue with pagination. Governance / audit.
5. Pitch script: `PRESENTATION.md` (also the in-app **Pitch** page).

## Run locally

```bash
cd dns-account-prep
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# set CEREBRAS_API_KEY
streamlit run app.py
```

Without an API key the crew still runs in **demo mode** (deterministic briefs + drafts).

## Streamlit Cloud

1. Push this folder (or the monorepo) to GitHub.
2. New app → set **Main file path** to `dns-account-prep/app.py` if the repo root is AISizing.
3. Secrets (Advanced):

```toml
CEREBRAS_API_KEY = "csk-..."
CEREBRAS_MODEL = "qwen-3.8-27b"
GOVERNANCE_ALLOW_CRM_WRITE = "false"
```

Optional:

```toml
MICROSERVICE_URL = "https://your-sizing-microservice"
MICROSERVICE_API_KEY = ""
HUBSPOT_ACCESS_TOKEN = ""
```

SQLite on Streamlit Cloud is ephemeral. Export accounts from **Governance** if you need a snapshot.

## Governance

| Action | Default |
|---|---|
| Local activity / tasks / drafts | Allowed |
| HubSpot notes | Off until `GOVERNANCE_ALLOW_CRM_WRITE=true` |
| Email / LinkedIn send | Not implemented — drafts only |
| Deal stage / forecast | Rep confirmation only |

## Cerebras

Get a key at [cloud.cerebras.ai](https://cloud.cerebras.ai). Pay-as-you-go starter credits apply. Model docs: [Qwen 3.8 27B](https://inference-docs.cerebras.ai/models/qwen-3.8-27b).
