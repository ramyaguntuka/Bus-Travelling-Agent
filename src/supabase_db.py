"""Save planner sessions in the Supabase Postgres table planner_sessions."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

_error = ""


def configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SECRET_KEY"))


def database_label() -> str:
    return "Supabase" if configured() else "local file"


def database_error() -> str:
    return _error


def fetch_session(session_id: str) -> dict | None:
    if not configured() or not session_id:
        return None
    try:
        response = _client().table("planner_sessions").select("*").eq("id", session_id).limit(1).execute()
    except Exception as exc:
        _remember(exc)
        return None
    _remember(None)
    rows = response.data or []
    if not rows:
        return None
    return _row_to_payload(rows[0])


def upsert_session(session_id: str, payload: dict) -> None:
    if not configured() or not session_id:
        return
    try:
        record = {
            "id": session_id,
            "profile": payload.get("profile") or {},
            "messages": payload.get("messages") or [],
            "summary": payload.get("summary") or "",
            "summary_mode": payload.get("summary_mode") or "local",
            "summary_error": payload.get("summary_error") or "",
            "last_plan": payload.get("last_plan") or "",
            "route_cities": payload.get("route_cities") or [],
            "route_line": payload.get("route_line") or [],
            "route_source": payload.get("route_source") or "",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _client().table("planner_sessions").upsert(record).execute()
    except Exception as exc:
        _remember(exc)
        return
    _remember(None)


def _client():
    from supabase import create_client

    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])


def _row_to_payload(row: dict) -> dict:
    return {
        "profile": row.get("profile") or {},
        "messages": row.get("messages") or [],
        "summary": row.get("summary") or "",
        "summary_mode": row.get("summary_mode") or "local",
        "summary_error": row.get("summary_error") or "",
        "last_plan": row.get("last_plan") or "",
        "route_cities": row.get("route_cities") or [],
        "route_line": row.get("route_line") or [],
        "route_source": row.get("route_source") or "",
    }


def _remember(exc: Exception | None) -> None:
    global _error
    if exc is None:
        _error = ""
        return
    text = str(exc).strip() or exc.__class__.__name__
    text = re.sub(r"sb_[A-Za-z0-9_\-]+", "[key]", text)
    _error = text[:240]