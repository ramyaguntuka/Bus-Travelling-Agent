"""Streamlit chat for the bus travel planner."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.catalog import known_cities, load_buses, load_places
from src.interview import apply_answer, apply_followup, chips_for, question_text, readback
from src.memory_store import session_from_disk, summarize_turn, write_session, answer_about_plan
from src.supabase_db import database_error, database_label
from src.osm_route import build_map, route_geometry
from src.planner import build_plan, ranked_routes

ROOT = Path(__file__).resolve().parent
SESSION_DIR = ROOT / "data" / "sessions"

load_dotenv(ROOT / ".env")


def main() -> None:
    st.set_page_config(page_title="Bus travel planner", layout="wide")
    st.title("Bus travel planner")
    st.caption("A few questions, then an optimized bus route and a day-by-day itinerary.")

    sid = _session_id()
    path = SESSION_DIR / f"{sid}.json"
    (
        profile,
        messages,
        summary,
        summary_mode,
        summary_error,
        last_plan,
        route_cities,
        route_line,
        route_source,
    ) = session_from_disk(path)
    if not messages:
        messages = [{"role": "assistant", "content": question_text(profile)}]
        write_session(
            path,
            profile,
            messages,
            summary,
            summary_mode,
            summary_error,
            last_plan,
            route_cities,
            route_line,
            route_source,
        )

    api_key = _sidebar(profile, summary, summary_mode, summary_error, path)
    buses = load_buses()
    places = load_places()
    cities = known_cities(buses)
    if profile.ready() and not route_line:
        routes = ranked_routes(profile, buses)
        if routes:
            route_cities = list(routes[0].cities)
            route_line, route_source = route_geometry(route_cities)
            write_session(
                path,
                profile,
                messages,
                summary,
                summary_mode,
                summary_error,
                last_plan,
                route_cities,
                route_line,
                route_source,
            )
    _show_route_map(route_cities, route_line, route_source)

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    chips = chips_for(profile)
    if chips:
        columns = st.columns(min(len(chips), 4))
        for index, chip in enumerate(chips):
            if columns[index % len(columns)].button(chip, key=f"chip-{len(messages)}-{index}"):
                st.session_state["pending_input"] = chip
                st.rerun()

    typed = st.chat_input("Your answer")
    incoming = st.session_state.pop("pending_input", None) or typed
    if not incoming:
        return

    with st.spinner("Checking your preferences and ranking buses..."):
        profile, messages, summary, summary_mode, summary_error, last_plan, route_cities, route_line, route_source = _handle(
            incoming,
            profile,
            messages,
            summary,
            summary_mode,
            summary_error,
            last_plan,
            route_cities,
            route_line,
            route_source,
            buses,
            places,
            cities,
            api_key,
        )
    write_session(
        path,
        profile,
        messages,
        summary,
        summary_mode,
        summary_error,
        last_plan,
        route_cities,
        route_line,
        route_source,
    )
    st.rerun()


def _handle(
    text,
    profile,
    messages,
    summary,
    summary_mode,
    summary_error,
    last_plan,
    route_cities,
    route_line,
    route_source,
    buses,
    places,
    cities,
    api_key,
):
    messages = list(messages)
    messages.append({"role": "user", "content": text})
    if not profile.ready():
        profile, error = apply_answer(profile, text, cities)
        if error:
            reply = f"{error}\n\n{question_text(profile)}"
        elif profile.ready():
            plan = build_plan(profile, buses, places, api_key, _context(summary, text))
            last_plan = plan.text
            route_cities, route_line, route_source = _geometry(plan.cities)
            reply = f"{readback(profile)}\n\n{last_plan}"
        else:
            reply = question_text(profile)
    else:
        profile, changed = apply_followup(profile, text, cities)
        if changed and profile.ready():
            plan = build_plan(profile, buses, places, api_key, _context(summary, text))
            last_plan = plan.text
            route_cities, route_line, route_source = _geometry(plan.cities)
            reply = f"Updated.\n\n{readback(profile)}\n\n{last_plan}"
        elif changed:
            route_cities, route_line, route_source = [], [], ""
            reply = question_text(profile)
        else:
            reply = answer_about_plan(api_key, summary, last_plan, text)
    messages.append({"role": "assistant", "content": reply})
    summary, summary_mode, summary_error = summarize_turn(api_key, summary, text, reply)
    return (
        profile,
        messages,
        summary,
        summary_mode,
        summary_error,
        last_plan,
        route_cities,
        route_line,
        route_source,
    )


def _geometry(cities: list[str]) -> tuple[list[str], list, str]:
    if len(cities) < 2:
        return [], [], ""
    line, source = route_geometry(cities)
    return cities, line, source


def _show_route_map(cities: list[str], line: list, source: str) -> None:
    if len(cities) < 2 or len(line) < 2:
        return
    st.subheader("Route on OpenStreetMap")
    if source == "osrm":
        st.caption("The line follows roads from OpenStreetMap. Numbered markers are the bus stops, in travel order.")
    else:
        st.caption("OpenStreetMap shows your stops. Road geometry was unavailable, so the line connects the cities directly.")
    from streamlit_folium import st_folium

    st_folium(
        build_map(cities, line),
        height=480,
        use_container_width=True,
        returned_objects=[],
        key="osm-" + "-".join(cities),
    )


def _context(summary: str, latest: str) -> str:
    latest = latest.strip()
    if summary and latest:
        return f"{summary}\nLatest answer: {latest}"
    return summary or latest


def _sidebar(profile, summary, summary_mode, summary_error, path: Path) -> str:
    stored = st.session_state.get("groq_api_key") or os.getenv("GROQ_API_KEY") or ""
    st.sidebar.header("Your trip")
    if stored:
        st.sidebar.success("Groq key loaded")
    else:
        st.sidebar.warning("No Groq key yet. Routes still rank. The itinerary uses the place catalog.")
    typed = st.sidebar.text_input("Groq API key", type="password")
    if typed:
        st.session_state["groq_api_key"] = typed.strip()
        stored = typed.strip()
    if summary_mode == "langchain":
        st.sidebar.caption("Memory: LangChain summary")
    else:
        st.sidebar.caption("Memory: local notes until Groq can summarize")
    st.sidebar.caption(f"Database: {database_label()}")
    if database_error():
        st.sidebar.caption(f"Database save failed ({database_error()}). A local copy is still kept.")
    if summary_error:
        st.sidebar.caption(f"Summary request failed ({summary_error}).")
    st.sidebar.markdown(summary or "No summary yet.")
    if profile.cities:
        st.sidebar.markdown("**Saved answers**")
        st.sidebar.write(" → ".join(profile.cities))
        if profile.travel_date or profile.date_flexible:
            when = profile.travel_date or "Flexible dates"
            st.sidebar.write(when)
        if profile.budget is not None:
            st.sidebar.write(f"Bus budget ₹{profile.budget:,}")
        if profile.priority:
            st.sidebar.write(f"Priority: {profile.priority}")
        if profile.seat_style or profile.ac:
            st.sidebar.write(f"{profile.ac or 'any'} · {profile.seat_style or 'any'}")
        if profile.pace:
            st.sidebar.write(f"{profile.pace} · {', '.join(profile.interests)}")
        if profile.avoids_confirmed:
            st.sidebar.write("Avoid: " + (", ".join(profile.avoids) if profile.avoids else "nothing"))
    if st.sidebar.button("Reset chat"):
        path.unlink(missing_ok=True)
        st.query_params["sid"] = uuid.uuid4().hex
        st.rerun()
    return stored


def _session_id() -> str:
    sid = st.query_params.get("sid", "")
    if isinstance(sid, list):
        sid = sid[0] if sid else ""
    if not re.fullmatch(r"[0-9a-f]{32}", sid or ""):
        sid = uuid.uuid4().hex
        st.query_params["sid"] = sid
    return sid


if __name__ == "__main__":
    main()