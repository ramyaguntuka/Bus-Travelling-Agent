"""Turn a finished profile into a route card and a day-by-day itinerary."""

from __future__ import annotations

from dataclasses import dataclass

from src.catalog import Place, known_cities
from src.itinerary import draft_itinerary, polish_itinerary, selected_place_names
from src.profile import TravelerProfile
from src.router import Bus, ScoredRoute, fmt_duration, rank_routes, rank_tour


@dataclass
class TripPlan:
    text: str
    cities: list[str]


def build_plan(
    profile: TravelerProfile,
    buses: list[Bus],
    places: dict[str, list[Place]],
    api_key: str | None,
    summary: str,
) -> TripPlan:
    cities = profile.cities[:6]
    routes = ranked_routes(profile, buses)
    if len(cities) < 2:
        return TripPlan("Tell me at least two cities and I will rank the buses.", [])
    if not routes:
        names = ", ".join(known_cities(buses))
        return TripPlan(
            "I could not find those cities connected in the sample network. "
            f"I can plan with: {names}.",
            [],
        )
    card = render_routes(routes, profile)
    draft = draft_itinerary(routes[0], profile, places, cities)
    allowed = selected_place_names(routes[0], profile, places, cities)
    catalog_names = {place.name for group in places.values() for place in group}
    polished = polish_itinerary(api_key, summary, draft, allowed, catalog_names)
    if polished and not all(leg.depart in polished for leg in routes[0].legs):
        polished = None
    return TripPlan(card + "\n" + (polished or draft), list(routes[0].cities))


def ranked_routes(profile: TravelerProfile, buses: list[Bus]) -> list[ScoredRoute]:
    cities = profile.cities[:6]
    if len(cities) < 2:
        return []
    if len(cities) == 2:
        return rank_routes(buses, cities[0], cities[1], profile, limit=3)
    return rank_tour(buses, cities, profile, limit=3)


def render_routes(routes: list[ScoredRoute], profile: TravelerProfile) -> str:
    best = routes[0]
    lines = [
        "### Recommended route",
        "",
        "Sample schedules, not live inventory. These buses are treated as running every day.",
        "",
    ]
    if best.relaxed_filters:
        lines.extend(
            [
                "I had to relax one of your bus preferences to find a connection.",
                "",
            ]
        )
    lines.append(" → ".join(best.cities))
    lines.append("")
    lines.append(_why(best, routes[1:], profile))
    lines.append("")
    lines.append(_totals(best, profile))
    lines.append("")
    lines.append(_legs_markdown(best))
    if routes[1:]:
        lines.extend(["", "### Alternatives", ""])
        for index, route in enumerate(routes[1:], start=2):
            lines.append(f"**Option {index}.** {' → '.join(route.cities)}")
            lines.append("")
            lines.append(_totals(route, profile))
            lines.append("")
            lines.append(_legs_markdown(route))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _totals(route: ScoredRoute, profile: TravelerProfile) -> str:
    transfer_word = "transfer" if route.transfers == 1 else "transfers"
    text = (
        f"₹{route.total_fare:,} total · {fmt_duration(route.ride_minutes)} in bus · "
        f"{route.transfers} {transfer_word}"
    )
    if route.travel_minutes != route.ride_minutes:
        text += f" · {fmt_duration(route.travel_minutes)} including connections"
    if profile.budget is not None and route.total_fare > profile.budget:
        text += f". This is over your ₹{profile.budget:,} bus budget."
    elif profile.budget is not None:
        text += f". Within your ₹{profile.budget:,} bus budget."
    return text


def _legs_markdown(route: ScoredRoute) -> str:
    lines = []
    for index, (leg, reason) in enumerate(zip(route.legs, route.reasons), start=1):
        seat = "AC" if leg.ac else "non-AC"
        lines.append(
            f"{index}. {leg.origin} → {leg.destination} · {leg.operator} · "
            f"depart {leg.depart}, arrive {leg.arrive} · {seat} {leg.seat_type} · "
            f"₹{leg.fare:,} · {fmt_duration(leg.duration_min)}"
        )
        lines.append(f"   {reason}.")
    return "\n".join(lines)


def _why(best: ScoredRoute, alternatives: list[ScoredRoute], profile: TravelerProfile) -> str:
    if not alternatives:
        return "Only connection in the sample network that fits this trip."
    nxt = alternatives[0]
    fare_gap = nxt.total_fare - best.total_fare
    time_gap = nxt.travel_minutes - best.travel_minutes
    if profile.priority == "cheapest" and fare_gap > 0:
        return f"₹{fare_gap:,} less than the next option."
    if profile.priority == "fastest" and time_gap > 0:
        return f"{fmt_duration(time_gap)} faster door to door than the next option."
    if profile.priority == "comfortable":
        return "Best comfort match for your seat type and departure window."
    if fare_gap > 0:
        return f"₹{fare_gap:,} less than the next option."
    return "Best overall score for your preferences."