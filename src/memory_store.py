"""LangChain conversation summary memory plus local session files."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from src.profile import TravelerProfile
from src.supabase_db import configured, fetch_session, upsert_session


def load_session(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def session_from_disk(path: Path) -> tuple[TravelerProfile, list[dict], str, str, str, str, list[str], list, str]:
    local = load_session(path)
    remote = fetch_session(path.stem)
    if remote:
        save_session(path, remote)
        raw = remote
    else:
        raw = local
        if local and configured():
            upsert_session(path.stem, local)
    profile = TravelerProfile.from_dict(raw.get("profile"))
    messages = list(raw.get("messages") or [])
    summary = raw.get("summary") or ""
    mode = raw.get("summary_mode") or "local"
    error = raw.get("summary_error") or ""
    last_plan = raw.get("last_plan") or ""
    route_cities = list(raw.get("route_cities") or [])
    route_line = list(raw.get("route_line") or [])
    route_source = raw.get("route_source") or ""
    return profile, messages, summary, mode, error, last_plan, route_cities, route_line, route_source


def write_session(
    path: Path,
    profile: TravelerProfile,
    messages: list[dict],
    summary: str,
    summary_mode: str,
    summary_error: str,
    last_plan: str,
    route_cities: list[str] | None = None,
    route_line: list | None = None,
    route_source: str = "",
) -> None:
    save_session(
        path,
        {
            "profile": profile.to_dict(),
            "messages": messages,
            "summary": summary,
            "summary_mode": summary_mode,
            "summary_error": summary_error,
            "last_plan": last_plan,
            "route_cities": route_cities or [],
            "route_line": route_line or [],
            "route_source": route_source,
        },
    )
    upsert_session(path.stem, load_session(path))


def summarize_turn(api_key: str | None, summary: str, user: str, assistant: str) -> tuple[str, str, str]:
    """Return the new summary, the mode, and an error string.

    With a Groq key this updates LangChain ConversationSummaryMemory.
    Without one, or if that call fails, a short local note is kept instead.
    """
    if api_key:
        try:
            memory = _summary_memory(api_key, summary)
            memory.save_context(
                {"input": user},
                {"output": _compact(assistant)},
            )
            updated = getattr(memory, "buffer", None)
            if not isinstance(updated, str) or not updated.strip():
                loaded = memory.load_memory_variables({})
                updated = loaded.get("history") or loaded.get("summary") or ""
                if not isinstance(updated, str):
                    updated = str(updated)
            if updated.strip():
                return updated.strip(), "langchain", ""
        except Exception as exc:
            fallback = _local_summary(summary, user)
            return fallback, "local", exc.__class__.__name__
    return _local_summary(summary, user), "local", ""


def answer_about_plan(api_key: str | None, summary: str, plan: str, question: str) -> str:
    if not api_key:
        return (
            "I can re-rank if you change the budget, the priority (cheapest, fastest, or comfortable), "
            "the seat style, what to avoid, or the cities. Ask me to adjust one of those and I will rebuild the plan."
        )
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.llm import make_chat

        model = make_chat(api_key, 0.2)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a bus travel planner. Answer from the traveler summary and the current plan. "
                        "Do not invent buses, fares, or sights. If the plan does not say, say so."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Summary:\n{summary or 'None yet.'}\n\n"
                        f"Current plan:\n{plan or 'No plan yet.'}\n\n"
                        f"Traveler: {question}"
                    )
                ),
            ]
        )
        text = getattr(response, "content", "") or ""
        if isinstance(text, list):
            text = "\n".join(str(part) for part in text)
        text = str(text).strip()
        if text:
            return text
    except Exception:
        pass
    return (
        "I kept the current plan. Tell me a new budget, priority, seat style, avoid, or route "
        "and I will rank the buses again."
    )


def _summary_memory(api_key: str, summary: str):
    from src.llm import make_chat

    try:
        from langchain.memory import ConversationSummaryMemory
    except ImportError:
        from langchain_classic.memory import ConversationSummaryMemory

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*ConversationSummaryMemory.*")
        memory = ConversationSummaryMemory(llm=make_chat(api_key, 0.1), return_messages=False)
    memory.buffer = summary or ""
    return memory


def _local_summary(summary: str, user: str) -> str:
    line = f"Traveler: {user.strip()}"
    text = f"{summary}\n{line}".strip()
    if len(text) > 2500:
        text = text[-2500:]
    return text


def _compact(assistant: str) -> str:
    text = " ".join(assistant.split())
    if len(text) > 2500:
        return text[:2500]
    return text