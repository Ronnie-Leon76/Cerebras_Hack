from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR, ROOT

DB_PATH = ROOT / "data" / "crm.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
          id TEXT PRIMARY KEY,
          customer_no TEXT,
          name TEXT NOT NULL,
          domain TEXT,
          country TEXT,
          city TEXT,
          type TEXT,
          segment TEXT,
          persona_title TEXT,
          persona_name TEXT,
          email TEXT,
          phone TEXT,
          strategic INTEGER DEFAULT 0,
          status TEXT DEFAULT 'open',
          last_activity_at TEXT,
          notes TEXT,
          signals TEXT,
          extra TEXT
        );
        CREATE TABLE IF NOT EXISTS drafts (
          id TEXT PRIMARY KEY,
          account_id TEXT,
          channel TEXT,
          subject TEXT,
          body TEXT,
          personalization TEXT,
          status TEXT,
          created_at TEXT,
          decided_at TEXT,
          decided_by TEXT
        );
        CREATE TABLE IF NOT EXISTS activities (
          id TEXT PRIMARY KEY,
          account_id TEXT,
          kind TEXT,
          detail TEXT,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          account_id TEXT,
          title TEXT,
          due_in_days INTEGER,
          status TEXT,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS notifications (
          id TEXT PRIMARY KEY,
          account_id TEXT,
          engineer TEXT,
          severity TEXT,
          play TEXT,
          title TEXT,
          body TEXT,
          status TEXT,
          created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit (
          id TEXT PRIMARY KEY,
          account_id TEXT,
          actor TEXT,
          action TEXT,
          payload TEXT,
          created_at TEXT
        );
        """
    )
    conn.commit()
    _seed_if_empty(conn)


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if n:
        return
    raw = json.loads((DATA_DIR / "accounts.json").read_text(encoding="utf-8"))
    for acc in raw:
        conn.execute(
            """
            INSERT INTO accounts (
              id, customer_no, name, domain, country, city, type, segment,
              persona_title, persona_name, email, phone, strategic, status,
              last_activity_at, notes, signals, extra
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                acc["id"],
                acc.get("customer_no"),
                acc["name"],
                acc.get("domain"),
                acc.get("country"),
                acc.get("city"),
                acc.get("type"),
                acc.get("segment"),
                acc.get("persona_title"),
                acc.get("persona_name"),
                acc.get("email"),
                acc.get("phone"),
                1 if acc.get("strategic") else 0,
                acc.get("status") or "open",
                acc.get("last_activity_at"),
                acc.get("notes"),
                json.dumps(acc.get("signals") or []),
                "{}",
            ),
        )
    conn.commit()


def list_accounts() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()
        return [_account(r) for r in rows]


def get_account_by_customer_no(customer_no: str) -> dict | None:
    if not customer_no:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE customer_no=?", (customer_no,)
        ).fetchone()
        return _account(row) if row else None


def search_accounts(q: str) -> list[dict]:
    ql = (q or "").lower().strip()
    if not ql:
        return list_accounts()
    out = []
    for acc in list_accounts():
        blob = " ".join(
            str(acc.get(k) or "")
            for k in ("name", "customer_no", "city", "country", "email", "phone", "persona_name")
        ).lower()
        if ql in blob:
            out.append(acc)
    return out


def list_activities(account_id: str, limit: int = 40) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM activities WHERE account_id=? ORDER BY created_at DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def add_notification(account_id: str, engineer: str, play: dict) -> str:
    nid = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?,?)",
            (
                nid,
                account_id,
                engineer,
                play.get("severity") or "medium",
                play.get("play") or "",
                play.get("title") or "",
                play.get("body") or "",
                "open",
                _now(),
            ),
        )
        conn.commit()
    log_audit(account_id, "crew", "notification", play.get("play"))
    return nid


def list_notifications(account_id: str | None = None, status: str | None = "open") -> list[dict]:
    with connect() as conn:
        sql = """
            SELECT n.*, a.name AS account_name, a.customer_no
            FROM notifications n LEFT JOIN accounts a ON a.id = n.account_id
            WHERE 1=1
        """
        params: list = []
        if account_id:
            sql += " AND n.account_id=?"
            params.append(account_id)
        if status:
            sql += " AND n.status=?"
            params.append(status)
        sql += " ORDER BY n.created_at DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def close_notification(nid: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE notifications SET status='done' WHERE id=?", (nid,))
        conn.commit()


def get_account(account_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        return _account(row) if row else None


def upsert_account(acc: dict) -> str:
    with connect() as conn:
        account_id = acc.get("id")
        if not account_id and acc.get("customer_no"):
            row = conn.execute(
                "SELECT id FROM accounts WHERE customer_no=?", (acc.get("customer_no"),)
            ).fetchone()
            if row:
                account_id = row["id"]
        account_id = account_id or f"acc-{uuid.uuid4().hex[:10]}"
        existing = conn.execute("SELECT id, extra FROM accounts WHERE id=?", (account_id,)).fetchone()
        extra = acc.get("extra")
        if extra is None:
            if existing:
                try:
                    extra = json.loads(existing["extra"] or "{}")
                except json.JSONDecodeError:
                    extra = {}
            else:
                extra = {}
        payload = (
            acc.get("customer_no"),
            acc.get("name"),
            acc.get("domain"),
            acc.get("country"),
            acc.get("city"),
            acc.get("type"),
            acc.get("segment"),
            acc.get("persona_title"),
            acc.get("persona_name"),
            acc.get("email"),
            acc.get("phone"),
            1 if acc.get("strategic") else 0,
            acc.get("status") or "open",
            acc.get("last_activity_at"),
            acc.get("notes"),
            json.dumps(acc.get("signals") or []),
            json.dumps(extra or {}),
            account_id,
        )
        if existing:
            conn.execute(
                """
                UPDATE accounts SET customer_no=?, name=?, domain=?, country=?, city=?,
                  type=?, segment=?, persona_title=?, persona_name=?, email=?, phone=?,
                  strategic=?, status=?, last_activity_at=?, notes=?, signals=?, extra=?
                WHERE id=?
                """,
                payload,
            )
        else:
            conn.execute(
                """
                INSERT INTO accounts (
                  customer_no, name, domain, country, city, type, segment,
                  persona_title, persona_name, email, phone, strategic, status,
                  last_activity_at, notes, signals, extra, id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                payload,
            )
        conn.commit()
    return account_id


def _account(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["strategic"] = bool(d.get("strategic"))
    try:
        d["signals"] = json.loads(d.get("signals") or "[]")
    except json.JSONDecodeError:
        d["signals"] = []
    try:
        d["extra"] = json.loads(d.get("extra") or "{}")
    except json.JSONDecodeError:
        d["extra"] = {}
    if not isinstance(d["extra"], dict):
        d["extra"] = {}
    d["last_prep"] = d["extra"].get("last_prep")
    d["sizing"] = (d["last_prep"] or {}).get("sizing") if isinstance(d.get("last_prep"), dict) else None
    return d


def log_audit(account_id: str | None, actor: str, action: str, payload: dict | str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit VALUES (?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                account_id,
                actor,
                action,
                json.dumps(payload) if not isinstance(payload, str) else payload,
                _now(),
            ),
        )
        conn.commit()


def list_audit(limit: int = 80) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def save_drafts(account_id: str, drafts: list[dict]) -> None:
    with connect() as conn:
        for d in drafts:
            conn.execute(
                """
                INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),
                    account_id,
                    d.get("channel"),
                    d.get("subject") or "",
                    d.get("body") or "",
                    json.dumps(d.get("personalization_vars") or []),
                    d.get("status") or "pending_approval",
                    _now(),
                    None,
                    None,
                ),
            )
        conn.commit()


def list_drafts(status: str | None = None) -> list[dict]:
    with connect() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT d.*, a.name AS account_name
                FROM drafts d LEFT JOIN accounts a ON a.id = d.account_id
                WHERE d.status=? ORDER BY d.created_at DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT d.*, a.name AS account_name
                FROM drafts d LEFT JOIN accounts a ON a.id = d.account_id
                ORDER BY d.created_at DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]


def update_draft_body(draft_id: str, subject: str, body: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE drafts SET subject=?, body=? WHERE id=?",
            (subject, body, draft_id),
        )
        conn.commit()


def save_last_prep(account_id: str, result: dict) -> None:
    acc = get_account(account_id)
    extra = dict((acc or {}).get("extra") or {})
    extra["last_prep"] = result
    extra["sizing"] = result.get("sizing")
    with connect() as conn:
        conn.execute(
            "UPDATE accounts SET extra=? WHERE id=?",
            (json.dumps(extra), account_id),
        )
        conn.commit()


def decide_draft(draft_id: str, status: str, actor: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE drafts SET status=?, decided_at=?, decided_by=? WHERE id=?",
            (status, _now(), actor, draft_id),
        )
        conn.commit()
    log_audit(None, actor, f"draft_{status}", {"draft_id": draft_id})


def add_activity(account_id: str, kind: str, detail: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO activities VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), account_id, kind, detail, _now()),
        )
        conn.execute(
            "UPDATE accounts SET last_activity_at=? WHERE id=?",
            (_now(), account_id),
        )
        conn.commit()


def add_task(account_id: str, title: str, due_in_days: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), account_id, title, due_in_days, "open", _now()),
        )
        conn.commit()


def stale_accounts(days: int = 14) -> list[dict]:
    cutoff_hint = days
    accounts = list_accounts()
    stale = []
    for acc in accounts:
        last = acc.get("last_activity_at")
        if not last:
            stale.append(acc)
            continue
        try:
            then = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - then).days
            if age >= cutoff_hint:
                stale.append(acc)
        except ValueError:
            stale.append(acc)
    return stale


def counts() -> dict[str, int]:
    with connect() as conn:
        accounts = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status='pending_approval'"
        ).fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE status='approved'"
        ).fetchone()[0]
        tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='open'").fetchone()[0]
        alerts = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE status='open'"
        ).fetchone()[0]
    ready = 0
    for acc in list_accounts():
        if acc.get("sizing") or (acc.get("last_prep") or {}).get("sizing"):
            ready += 1
    return {
        "accounts": accounts,
        "pending_drafts": pending,
        "approved_drafts": approved,
        "open_tasks": tasks,
        "stale": len(stale_accounts()),
        "sizing_tickets": ready,
        "alerts": alerts,
    }
