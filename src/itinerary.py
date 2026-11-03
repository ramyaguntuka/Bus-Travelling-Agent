"""Day-by-day itinerary grounded in the bus legs and the place catalog."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from src.catalog import Place
from src.profile import TravelerProfile
from src.router import ScoredRoute, chain_times, fmt_clock, fmt_duration

PERIODS = (
    ("Morning", 0, 12 * 60),
    ("Afternoon", 12 * 60, 17 * 60),
    ("Evening", 17 * 60, 24 * 60),
)


def draft_itinerary(
    route: ScoredRoute,
    profile: TravelerProfile,
    places: dict[str, list[Place]],
    planned_stops: list[str] | None = None,
) -> str:
    blocks = _blocks(route, profile, places, planned_stops or profile.cities)
    return _render(blocks, profile.travel_date)


def selected_place_names(
    route: ScoredRoute,
    profile: TravelerProfile,
    places: dict[str, list[Place]],
    planned_stops: list[str] | None = None,
) -> list[str]:
    blocks = _blocks(route, profile, places, planned_stops or profile.cities)
    names = []
    for block in blocks:
        if block["kind"] == "activity":
            names.append(block["place"])
    return names


def _blocks(
    route: ScoredRoute,
    profile: TravelerProfile,
    places: dict[str, list[Place]],
    planned_stops: list[str],
) -> list[dict]:
    times = chain_times(route.legs)
    planned = set(planned_stops)
    blocks: list[dict] = []
    for index, leg in enumerate(route.legs):
        depart_abs, arrive_abs = times[index]
        seat = "AC" if leg.ac else "non-AC"
        blocks.append(
            {
                "day": depart_abs // 1440,
                "start": depart_abs % 1440,
                "kind": "bus",
                "place": "",
                "text": (
                    f"{fmt_clock(depart_abs)}–{leg.arrive} · {leg.operator} · "
                    f"{leg.origin} → {leg.destination} · {seat} {leg.seat_type} · "
                    f"₹{leg.fare:,} · {fmt_duration(leg.duration_min)}"
                ),
            }
        )
        if arrive_abs // 1440 != depart_abs // 1440:
            blocks.append(
                {
                    "day": arrive_abs // 1440,
                    "start": arrive_abs % 1440,
                    "kind": "arrival",
                    "place": "",
                    "text": f"Arrive in {leg.destination} at {fmt_clock(arrive_abs)}.",
                }
            )
        if index + 1 < len(route.legs):
            next_depart = times[index + 1][0]
            _fill_stop(
                blocks,
                leg.destination,
                arrive_abs,
                next_depart,
                planned,
                profile,
                places,
                final=False,
            )
        else:
            _fill_stop(
                blocks,
                leg.destination,
                arrive_abs,
                None,
                planned,
                profile,
                places,
                final=True,
            )
    blocks.sort(key=lambda block: (block["day"], block["start"], block["kind"] != "bus"))
    return blocks


def _fill_stop(
    blocks: list[dict],
    city: str,
    arrive_abs: int,
    next_depart: int | None,
    planned: set[str],
    profile: TravelerProfile,
    places: dict[str, list[Place]],
    final: bool,
) -> None:
    if next_depart is None:
        slices = _final_slices(arrive_abs)
    else:
        gap = next_depart - arrive_abs
        if city not in planned or gap < 4 * 60:
            if gap >= 45 and city not in planned:
                blocks.append(
                    {
                        "day": arrive_abs // 1440,
                        "start": arrive_abs % 1440,
                        "kind": "note",
                        "place": "",
                        "text": f"Short transfer in {city}. No sightseeing on this connection.",
                    }
                )
            return
        slices = _usable_slices(arrive_abs, next_depart)

    if not slices:
        return
    remaining = [list(item) for item in slices]
    chosen = _pick_places(city, profile, places, remaining)
    for place, start_abs, _end_abs in chosen:
        blocks.append(
            {
                "day": start_abs // 1440,
                "start": start_abs % 1440,
                "kind": "activity",
                "place": place.name,
                "text": f"{place.name} · about { _hours(place.hours) } · {', '.join(place.tags)}",
            }
        )
    for start_abs, end_abs in remaining:
        if end_abs - start_abs >= 45:
            blocks.append(
                {
                    "day": start_abs // 1440,
                    "start": start_abs % 1440,
                    "kind": "free",
                    "place": "",
                    "text": f"Free time in {city} · {fmt_duration(end_abs - start_abs)} open.",
                }
            )


def _final_slices(arrive_abs: int) -> list[tuple[int, int]]:
    day = arrive_abs // 1440
    clock = arrive_abs % 1440
    if clock <= 18 * 60:
        end = day * 1440 + 21 * 60
        usable = _usable_slices(arrive_abs, end)
        if usable:
            return usable
    next_day = day + 1
    return [(next_day * 1440 + 9 * 60, next_day * 1440 + 13 * 60)]


def _usable_slices(start_abs: int, end_abs: int) -> list[tuple[int, int]]:
    bounds = ((8 * 60, 12 * 60), (12 * 60, 17 * 60), (17 * 60, 21 * 60))
    slices = []
    first_day = start_abs // 1440
    last_day = end_abs // 1440
    for day in range(first_day, last_day + 1):
        for open_min, close_min in bounds:
            start = max(start_abs, day * 1440 + open_min)
            end = min(end_abs, day * 1440 + close_min)
            if end - start >= 90:
                slices.append((start, end))
    return slices


def _period(start_abs: int) -> str:
    clock = start_abs % 1440
    if clock < 12 * 60:
        return "morning"
    if clock < 17 * 60:
        return "afternoon"
    return "evening"


def _pick_places(
    city: str,
    profile: TravelerProfile,
    places: dict[str, list[Place]],
    slices: list[list[int]],
) -> list[tuple[Place, int, int]]:
    options = list(places.get(city, []))
    interests = set(profile.interests)

    def overlap(place: Place) -> int:
        return len(set(place.tags) & interests)

    if any(overlap(place) > 0 for place in options):
        options = [place for place in options if overlap(place) > 0]
    options.sort(key=lambda place: (-overlap(place), place.hours if profile.pace == "packed" else -place.hours))
    limit = 3 if profile.pace == "packed" else 2
    chosen: list[tuple[Place, int, int]] = []
    for place in options:
        if len(chosen) >= limit:
            break
        needed = int(place.hours * 60)
        candidates = []
        for slice_index, (start, end) in enumerate(slices):
            if end - start >= needed:
                prefer = 0 if place.slot in (_period(start), "any", "") else 1
                candidates.append((prefer, start, slice_index))
        if not candidates:
            continue
        _, _, slice_index = min(candidates)
        start, _end = slices[slice_index]
        chosen.append((place, start, start + needed))
        slices[slice_index][0] = start + needed
    return chosen


def _render(blocks: list[dict], travel_date: str | None) -> str:
    if not blocks:
        return "### Day-by-day itinerary\n\nNo free time around these buses."
    days = sorted({block["day"] for block in blocks})
    lines = ["### Day-by-day itinerary", ""]
    for day in days:
        lines.append(f"#### {_day_label(day, travel_date)}")
        lines.append("")
        day_blocks = [block for block in blocks if block["day"] == day]
        for label, start, end in PERIODS:
            group = [block for block in day_blocks if start <= block["start"] < end]
            if not group:
                continue
            lines.append(f"**{label}**")
            lines.append("")
            for block in group:
                lines.append(f"- {block['text']}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _day_label(day_index: int, travel_date: str | None) -> str:
    if not travel_date:
        return f"Day {day_index + 1}"
    start = datetime.strptime(travel_date, "%Y-%m-%d").date()
    current = start + timedelta(days=day_index)
    return f"Day {day_index + 1} · {_pretty(current)}"


def _pretty(current: date) -> str:
    return f"{current.strftime('%A')} {current.day} {current.strftime('%b %Y')}"


def _hours(value: float) -> str:
    if value == int(value):
        number = str(int(value))
    else:
        number = f"{value:g}"
    unit = "hour" if value == 1 else "hours"
    return f"{number} {unit}"


def polish_itinerary(api_key: str | None, summary: str, draft: str, allowed_places: list[str], catalog_names: set[str]) -> str | None:
    if not api_key:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.llm import make_chat

        model = make_chat(api_key, 0.3)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You write day-by-day bus trip itineraries in markdown. "
                        "Use only the buses, times, fares, and places in the draft. "
                        "Do not invent sights, operators, or departure times. "
                        "Keep Morning, Afternoon, and Evening headings only for parts of the day that have plans. "
                        "Keep every departure time and every place name from the draft. "
                        "Mention free time when the draft has it."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Traveler summary:\n{summary or 'No earlier summary.'}\n\n"
                        f"Rewrite this itinerary:\n\n{draft}"
                    )
                ),
            ]
        )
        text = getattr(response, "content", "") or ""
        if isinstance(text, list):
            text = "\n".join(str(part) for part in text)
        if _acceptable(str(text), allowed_places, catalog_names):
            body = str(text).strip()
            if not body.startswith("###"):
                body = "### Day-by-day itinerary\n\n" + body
            return body + ("\n" if not body.endswith("\n") else "")
    except Exception:
        return None
    return None


def _acceptable(text: str, allowed_places: list[str], catalog_names: set[str]) -> bool:
    if len(text.strip()) < 40:
        return False
    for name in allowed_places:
        if name not in text:
            return False
    for name in catalog_names - set(allowed_places):
        if name and name in text:
            return False
    return True