"""Preference-weighted bus ranking.

Hard filters (night sleeper, AC, no early departures, no long unplanned layovers)
drop options only when another feasible bus or path remains. Otherwise the same
preference becomes a penalty and the route is marked relaxed.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Bus:
    id: str
    origin: str
    destination: str
    operator: str
    depart: str
    arrive: str
    duration_min: int
    fare: int
    seat_type: str
    ac: bool
    comfort: int


@dataclass
class ScoredRoute:
    legs: list[Bus]
    score: float
    total_fare: int
    travel_minutes: int
    ride_minutes: int
    transfers: int
    cities: list[str]
    reasons: list[str]
    relaxed_filters: bool


def minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def fmt_clock(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def fmt_duration(total: int) -> str:
    hours, mins = divmod(int(total), 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def chain_times(legs: Sequence[Bus]) -> list[tuple[int, int]]:
    """Absolute depart and arrive minutes from midnight of the first boarding day."""
    times: list[tuple[int, int]] = []
    for index, leg in enumerate(legs):
        depart_clock = minutes(leg.depart)
        if index == 0:
            depart_abs = depart_clock
        else:
            previous_arrival = times[-1][1]
            depart_abs = depart_clock
            while depart_abs < previous_arrival + 30:
                depart_abs += 24 * 60
        times.append((depart_abs, depart_abs + leg.duration_min))
    return times


def connection_gaps(legs: Sequence[Bus]) -> list[int]:
    times = chain_times(legs)
    return [times[index + 1][0] - times[index][1] for index in range(len(legs) - 1)]


def _weights(priority: str | None) -> dict[str, float]:
    if priority == "cheapest":
        return {"duration": 0.15, "fare": 0.55, "transfers": 0.10, "window": 0.10, "comfort": 0.10}
    if priority == "fastest":
        return {"duration": 0.50, "fare": 0.10, "transfers": 0.25, "window": 0.05, "comfort": 0.10}
    return {"duration": 0.15, "fare": 0.10, "transfers": 0.10, "window": 0.25, "comfort": 0.40}


def window_mismatch(bus: Bus, profile) -> float:
    depart = minutes(bus.depart)
    if profile.seat_style == "night_sleeper":
        if 19 * 60 <= depart <= 23 * 60 + 30:
            mismatch = 0.0
        elif depart < 8 * 60:
            mismatch = 1.0
        else:
            mismatch = 0.45
    elif profile.seat_style == "day_seater":
        mismatch = 0.0 if 8 * 60 <= depart <= 18 * 60 else 1.0
    else:
        mismatch = 0.0
    if "early_departures" in profile.avoids and depart < 8 * 60:
        mismatch = max(mismatch, 1.0)
    return mismatch


def comfort_mismatch(bus: Bus, profile) -> float:
    score = 1 - (bus.comfort / 5)
    if profile.seat_style == "night_sleeper" and bus.seat_type != "sleeper":
        score += 0.5
    if profile.seat_style == "day_seater" and bus.seat_type != "seater":
        score += 0.5
    wants_ac = profile.ac == "ac" or "non_ac" in profile.avoids
    if wants_ac and not bus.ac:
        score += 0.5
    if profile.ac == "non_ac" and bus.ac:
        score += 0.25
    return min(score, 1.5)


def _norm(values: Sequence[float], value: float) -> float:
    low, high = min(values), max(values)
    if high == low:
        return 0.0
    return (value - low) / (high - low)


def _index(buses: Iterable[Bus]) -> dict[tuple[str, str], list[Bus]]:
    grouped: dict[tuple[str, str], list[Bus]] = {}
    for bus in buses:
        grouped.setdefault((bus.origin, bus.destination), []).append(bus)
    return grouped


def _apply(options: list[Bus], predicate) -> tuple[list[Bus], bool]:
    kept = [bus for bus in options if predicate(bus)]
    if kept:
        return kept, False
    return options, True


def filter_edge(options: list[Bus], profile) -> tuple[list[Bus], bool]:
    if not options:
        return [], False
    chosen = list(options)
    relaxed = False
    if profile.seat_style == "night_sleeper":
        chosen, softened = _apply(
            chosen,
            lambda bus: minutes(bus.depart) >= 18 * 60 and bus.seat_type == "sleeper",
        )
        relaxed = relaxed or softened
    elif profile.seat_style == "day_seater":
        chosen, softened = _apply(
            chosen,
            lambda bus: bus.seat_type == "seater" and 8 * 60 <= minutes(bus.depart) <= 18 * 60,
        )
        relaxed = relaxed or softened
    if profile.ac == "ac" or "non_ac" in profile.avoids:
        chosen, softened = _apply(chosen, lambda bus: bus.ac)
        relaxed = relaxed or softened
    elif profile.ac == "non_ac":
        chosen, softened = _apply(chosen, lambda bus: not bus.ac)
        relaxed = relaxed or softened
    if "early_departures" in profile.avoids:
        chosen, softened = _apply(chosen, lambda bus: minutes(bus.depart) >= 8 * 60)
        relaxed = relaxed or softened
    return chosen, relaxed


def _preliminary(bus: Bus, profile) -> float:
    weights = _weights(profile.priority)
    return (
        weights["duration"] * (bus.duration_min / 1440)
        + weights["fare"] * (bus.fare / 5000)
        + weights["window"] * window_mismatch(bus, profile)
        + weights["comfort"] * comfort_mismatch(bus, profile)
    )


def _city_paths(index: dict[tuple[str, str], list[Bus]], origin: str, destination: str) -> list[list[str]]:
    paths: list[list[str]] = []
    stack = [(origin, [origin])]
    while stack:
        city, path = stack.pop()
        if len(path) > 1 and city == destination:
            paths.append(path)
            continue
        if len(path) - 1 >= 3:
            continue
        neighbors = sorted({dest for src, dest in index if src == city})
        for nxt in neighbors:
            if nxt not in path:
                stack.append((nxt, path + [nxt]))
    paths.sort(key=len)
    return paths[:40]


def _edge_choices(index, origin: str, destination: str, profile) -> tuple[list[Bus], bool]:
    chosen, relaxed = filter_edge(index.get((origin, destination), []), profile)
    chosen = sorted(chosen, key=lambda bus: _preliminary(bus, profile))[:3]
    return chosen, relaxed


def explain_leg(bus: Bus, siblings: Sequence[Bus], profile) -> str:
    notes: list[str] = []
    compared = len(siblings) > 1
    if compared and bus.fare == min(item.fare for item in siblings):
        notes.append(f"lowest fare on this sector (₹{bus.fare:,})")
    elif compared and bus.duration_min == min(item.duration_min for item in siblings):
        notes.append("shortest ride on this sector")
    if (
        profile.seat_style == "night_sleeper"
        and bus.seat_type == "sleeper"
        and minutes(bus.depart) >= 18 * 60
    ):
        notes.append("night sleeper in your evening window")
    if profile.seat_style == "day_seater" and bus.seat_type == "seater":
        notes.append("day seater as requested")
    if profile.priority == "comfortable" and compared and bus.comfort == max(item.comfort for item in siblings):
        notes.append(f"highest comfort rating ({bus.comfort}/5)")
    if (profile.ac == "ac" or "non_ac" in profile.avoids) and bus.ac:
        notes.append("AC")
    if not notes:
        notes.append("best overall match for your priority on this sector")
    unique: list[str] = []
    for note in notes:
        if note not in unique:
            unique.append(note)
    return "; ".join(unique)


def _travel_minutes(legs: Sequence[Bus], planned: set[str]) -> int:
    total = sum(leg.duration_min for leg in legs)
    for leg, gap in zip(legs[:-1], connection_gaps(legs)):
        if leg.destination not in planned:
            total += gap
    return total


def _transfers(legs: Sequence[Bus], planned: set[str]) -> int:
    return sum(1 for leg in legs[:-1] if leg.destination not in planned)


def _long_unplanned_layover(legs: Sequence[Bus], planned: set[str]) -> bool:
    for leg, gap in zip(legs[:-1], connection_gaps(legs)):
        if leg.destination not in planned and gap > 240:
            return True
    return False


def _short_planned_stays(legs: Sequence[Bus], planned: set[str]) -> int:
    final = legs[-1].destination
    count = 0
    for leg, gap in zip(legs[:-1], connection_gaps(legs)):
        if leg.destination in planned and leg.destination != final and gap < 8 * 60:
            count += 1
    return count


def _score(
    journeys: list[list[Bus]],
    profile,
    planned: set[str],
    relaxed: bool,
    index,
) -> list[ScoredRoute]:
    if not journeys:
        return []
    fares = [sum(bus.fare for bus in legs) for legs in journeys]
    travels = [_travel_minutes(legs, planned) for legs in journeys]
    weights = _weights(profile.priority)
    scored: list[ScoredRoute] = []
    for legs, fare, travel in zip(journeys, fares, travels):
        windows = sum(window_mismatch(bus, profile) for bus in legs) / len(legs)
        comforts = sum(comfort_mismatch(bus, profile) for bus in legs) / len(legs)
        transfers = _transfers(legs, planned)
        over_budget = 0.0
        if profile.budget is not None and fare > profile.budget:
            over_budget = 0.8 if profile.priority == "cheapest" else 0.35
        score = (
            weights["duration"] * _norm(travels, travel)
            + weights["fare"] * _norm(fares, fare)
            + weights["transfers"] * min(transfers, 2) / 2
            + weights["window"] * min(windows, 1)
            + weights["comfort"] * min(comforts, 1.5) / 1.5
            + over_budget
            + 0.35 * _short_planned_stays(legs, planned)
        )
        reasons = []
        for leg in legs:
            siblings, _ = filter_edge(index.get((leg.origin, leg.destination), []), profile)
            reasons.append(explain_leg(leg, siblings, profile))
        scored.append(
            ScoredRoute(
                legs=list(legs),
                score=score,
                total_fare=fare,
                travel_minutes=travel,
                ride_minutes=sum(bus.duration_min for bus in legs),
                transfers=transfers,
                cities=[legs[0].origin, *[leg.destination for leg in legs]],
                reasons=reasons,
                relaxed_filters=relaxed,
            )
        )
    scored.sort(key=lambda route: (round(route.score, 6), route.total_fare, route.travel_minutes))
    unique: list[ScoredRoute] = []
    seen: set[tuple[str, ...]] = set()
    for route in scored:
        key = tuple(bus.id for bus in route.legs)
        if key in seen:
            continue
        seen.add(key)
        unique.append(route)
    return unique


def rank_routes(buses: Sequence[Bus], origin: str, destination: str, profile, limit: int = 3) -> list[ScoredRoute]:
    if not origin or not destination or origin == destination:
        return []
    index = _index(buses)
    paths = _city_paths(index, origin, destination)
    tagged: list[tuple[list[Bus], bool]] = []
    seen: set[tuple[str, ...]] = set()
    for path in paths:
        edge_lists: list[list[Bus]] = []
        path_relaxed = False
        missing = False
        for start, end in zip(path, path[1:]):
            choices, edge_relaxed = _edge_choices(index, start, end, profile)
            if not choices:
                missing = True
                break
            path_relaxed = path_relaxed or edge_relaxed
            edge_lists.append(choices)
        if missing:
            continue
        for combo in product(*edge_lists):
            legs = list(combo)
            key = tuple(bus.id for bus in legs)
            if key in seen:
                continue
            seen.add(key)
            tagged.append((legs, path_relaxed))

    strict = [legs for legs, relaxed in tagged if not relaxed]
    relaxed = not strict
    pool = strict if strict else [legs for legs, _ in tagged]
    planned = {origin, destination}
    if pool and "long_layovers" in profile.avoids:
        short = [legs for legs in pool if not _long_unplanned_layover(legs, planned)]
        if short:
            pool = short
        else:
            relaxed = True
    ranked = _score(pool, profile, planned, relaxed, index)
    for route in ranked:
        route.relaxed_filters = relaxed
    return ranked[:limit]


def rank_tour(buses: Sequence[Bus], cities: Sequence[str], profile, limit: int = 3) -> list[ScoredRoute]:
    ordered = [city for city in cities if city]
    if len(ordered) < 2:
        return []
    if len(ordered) == 2:
        return rank_routes(buses, ordered[0], ordered[1], profile, limit=limit)
    if len(ordered) > 6:
        ordered = ordered[:6]

    start, *rest = ordered
    planned = set(ordered)
    index = _index(buses)
    tagged: list[tuple[list[Bus], bool]] = []
    seen: set[tuple[str, ...]] = set()
    for perm in permutations(rest):
        order = [start, *perm]
        if any(left == right for left, right in zip(order, order[1:])):
            continue
        hop_choices: list[list[ScoredRoute]] = []
        possible = True
        for index_hop, (origin, destination) in enumerate(zip(order, order[1:])):
            later = set(order[index_hop + 2 :])
            options = [
                option
                for option in rank_routes(buses, origin, destination, profile, limit=2)
                if not any(leg.destination in later for leg in option.legs[:-1])
            ]
            if not options:
                possible = False
                break
            hop_choices.append(options)
        if not possible:
            continue
        for combo in product(*hop_choices):
            legs = [leg for option in combo for leg in option.legs]
            key = tuple(bus.id for bus in legs)
            if key in seen:
                continue
            seen.add(key)
            tagged.append((legs, any(option.relaxed_filters for option in combo)))

    strict = [legs for legs, relaxed in tagged if not relaxed]
    relaxed = not strict
    pool = strict if strict else [legs for legs, _ in tagged]
    if pool and "long_layovers" in profile.avoids:
        short = [legs for legs in pool if not _long_unplanned_layover(legs, planned)]
        if short:
            pool = short
        else:
            relaxed = True
    ranked = _score(pool, profile, planned, relaxed, index)
    for route in ranked:
        route.relaxed_filters = relaxed
    return ranked[:limit]