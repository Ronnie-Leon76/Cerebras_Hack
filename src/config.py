from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"


def _secret(name: str, default: str = "") -> str:
    secrets_files = (
        Path.home() / ".streamlit" / "secrets.toml",
        ROOT / ".streamlit" / "secrets.toml",
    )
    if any(p.is_file() for p in secrets_files):
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            import streamlit as st

            if get_script_run_ctx() is not None and name in st.secrets:
                return str(st.secrets[name])
        except Exception:
            pass
    return os.getenv(name, default)


def cerebras_api_key() -> str:
    return _secret("CEREBRAS_API_KEY").strip()


def cerebras_model() -> str:
    return _secret("CEREBRAS_MODEL", "qwen-3.8-27b").strip() or "qwen-3.8-27b"


def allow_crm_write() -> bool:
    return _secret("GOVERNANCE_ALLOW_CRM_WRITE", "false").lower() in {"1", "true", "yes"}


def auto_approve_nonstrategic() -> bool:
    return _secret("GOVERNANCE_AUTO_APPROVE_NONSTRATEGIC", "false").lower() in {
        "1",
        "true",
        "yes",
    }


def hubspot_token() -> str:
    return _secret("HUBSPOT_ACCESS_TOKEN").strip()


def microservice_url() -> str:
    return _secret("MICROSERVICE_URL").strip().rstrip("/")


def microservice_api_key() -> str:
    return _secret("MICROSERVICE_API_KEY").strip()


def sizing_base_url() -> str:
    return (
        _secret("SIZING_BASE_URL", "https://sizing.dayliff.com").strip().rstrip("/")
        or "https://sizing.dayliff.com"
    )


def bc_url() -> str:
    return _secret("BC_URL").strip().rstrip("/")


def bc_username() -> str:
    return _secret("BC_USERNAME", _secret("BC_USER")).strip()


def bc_password() -> str:
    return _secret("BC_PASSWORD").strip()


def notify_engineer_email() -> str:
    return _secret("ENGINEER_NOTIFY_EMAIL").strip()


def smtp_host() -> str:
    return _secret("SMTP_HOST").strip()


def smtp_user() -> str:
    return _secret("SMTP_USER").strip()


def smtp_password() -> str:
    return _secret("SMTP_PASSWORD").strip()

