from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import notify_engineer_email, smtp_host, smtp_password, smtp_user


def send_play_email(play: dict, account_name: str) -> dict:
    to = notify_engineer_email()
    host = smtp_host()
    if not to:
        return {"ok": False, "reason": "ENGINEER_NOTIFY_EMAIL not set — in-app alert only"}
    if not host:
        return {
            "ok": False,
            "reason": "SMTP_HOST not set — alert stored in CRM; copy the body to WhatsApp/email",
            "mailto": f"mailto:{to}?subject={play.get('title','')}&body={play.get('body','')[:800]}",
        }
    msg = EmailMessage()
    msg["Subject"] = f"[D&S Account Prep] {play.get('title')}"
    msg["From"] = smtp_user() or "account-prep@dayliff.local"
    msg["To"] = to
    msg.set_content(
        f"Account: {account_name}\nPlay: {play.get('play')}\nSeverity: {play.get('severity')}\n\n{play.get('body')}\n"
    )
    try:
        with smtplib.SMTP(host, 587, timeout=12) as s:
            s.starttls()
            if smtp_user():
                s.login(smtp_user(), smtp_password())
            s.send_message(msg)
        return {"ok": True, "to": to}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
