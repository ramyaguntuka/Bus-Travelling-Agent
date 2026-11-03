"""Short question flow that fills traveler slots before any route is ranked."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from src.profile import TravelerProfile

ALIASES = {
    "new delhi": "delhi",
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "madras": "chennai",
    "cochin": "kochi",
    "panaji": "goa",
    "panjim": "goa",
}

INTERESTS = ("heritage", "food", "nature", "shopping")

PROMPTS = {
    "route": (
        "Where are you traveling? Give me a start and an end, or list up to six cities "
        "and I will order the stops. For example: Delhi to Jaipur, or Delhi, Jaipur, Udaipur."
    ),
    "date": (
        "What date do you want to start? You can name a date, say a day either side is fine, "
        "or leave the dates flexible."
    ),
    "budget": "What is your bus budget per person, in rupees?",
    "seat": "What kind of bus do you want?",
    "priority": "What should I optimize for?",
    "style": (
        "How do you like the days on the ground? Tell me the pace (relaxed or packed) and "
        "what you care about: heritage, food, nature, shopping."
    ),
    "avoids": "Anything I should avoid? Early departures, long layovers, non-AC buses — or nothing.",
}

CHIPS = {
    "route": ["Delhi to Jaipur", "Mumbai to Goa", "Bengaluru to Chennai", "Delhi, Jaipur, Udaipur"],
    "date": ["Flexible dates", "Next Friday", "This weekend"],
    "budget": ["Under ₹1,500", "Around ₹3,000", "Up to ₹8,000"],
    "seat": ["Night AC sleeper", "Day AC seater", "Any AC bus", "Non-AC is fine"],
    "priority": ["Cheapest", "Fastest", "Most comfortable"],
    "style": [
        "Relaxed, heritage and food",
        "Packed, food and shopping",
        "Relaxed, nature",
        "Packed, heritage",
    ],
    "avoids": ["Nothing to avoid", "No early departures", "No long layovers", "AC only"],
}


def question_text(profile: TravelerProfile) -> str:
    step = profile.missing_step()
    if step is None:
        return "Tell me what to change and I will re-rank the buses."
    if step == "seat" and profile.seat_style and not profile.ac:
        return "Do you want AC, or is non-AC fine?"
    if step == "seat" and profile.ac and not profile.seat_style:
        return "Night sleeper, day seater, or no seat preference?"
    if step == "style" and profile.pace and not profile.interests:
        return "Which of these interest you: heritage, food, nature, shopping?"
    if step == "style" and profile.interests and not profile.pace:
        return "Do you want a relaxed pace or a packed one?"
    return PROMPTS[step]


def chips_for(profile: TravelerProfile) -> list[str]:
    step = profile.missing_step()
    if step is None:
        return []
    if step == "seat" and profile.ac and not profile.seat_style:
        return ["Night sleeper", "Day seater", "No preference"]
    if step == "style" and profile.pace and not profile.interests:
        return ["Heritage and food", "Food and shopping", "Nature", "A bit of everything"]
    if step == "style" and profile.interests and not profile.pace:
        return ["Relaxed", "Packed"]
    return list(CHIPS[step])


def readback(profile: TravelerProfile) -> str:
    route = " → ".join(profile.cities)
    if profile.travel_date:
        when = profile.travel_date
        if profile.date_flexible:
            when += " (a day either side is fine)"
    else:
        when = "flexible dates"
    seat = {
        "night_sleeper": "night sleeper",
        "day_seater": "day seater",
        "any": "no seat preference",
    }.get(profile.seat_style or "", "a bus")
    ac = {"ac": "AC", "non_ac": "non-AC", "any": "AC or non-AC"}.get(profile.ac or "", "AC or non-AC")
    avoids = ", ".join(_avoid_label(item) for item in profile.avoids) if profile.avoids else "nothing in particular"
    interests = ", ".join(profile.interests)
    budget = f"₹{profile.budget:,}" if profile.budget is not None else "an open budget"
    return (
        f"Here is what I will optimize for: {route}, starting {when}, "
        f"bus budget {budget}, {ac} {seat}, priority {profile.priority}, "
        f"{profile.pace} pace, interests {interests}, avoid {avoids}."
    )


def apply_answer(
    profile: TravelerProfile,
    text: str,
    known_cities: list[str],
    today: date | None = None,
) -> tuple[TravelerProfile, str | None]:
    step = profile.missing_step()
    if step is None:
        return profile, None
    updated = profile.clone()
    parsers = {
        "route": lambda: _parse_route(updated, text, known_cities),
        "date": lambda: _parse_date(updated, text, today or date.today()),
        "budget": lambda: _parse_budget(updated, text),
        "seat": lambda: _parse_seat(updated, text),
        "priority": lambda: _parse_priority(updated, text),
        "style": lambda: _parse_style(updated, text),
        "avoids": lambda: _parse_avoids(updated, text),
    }
    error = parsers[step]()
    if error:
        return profile, error
    return updated, None


def apply_followup(
    profile: TravelerProfile,
    text: str,
    known_cities: list[str],
    today: date | None = None,
) -> tuple[TravelerProfile, bool]:
    updated = profile.clone()
    changed = False
    found = extract_cities(text, known_cities)
    if len(found) >= 2 and found != updated.cities:
        updated.cities = found[:6]
        updated.origin = found[0]
        updated.destination = found[-1]
        changed = True

    probed = TravelerProfile()
    if _parse_date(probed, text, today or date.today()) is None and (
        probed.travel_date or probed.date_flexible
    ):
        if probed.travel_date != updated.travel_date or probed.date_flexible != updated.date_flexible:
            updated.travel_date = probed.travel_date
            updated.date_flexible = probed.date_flexible or updated.date_flexible
            changed = True

    amount = _budget_amount(text)
    if amount is not None and amount != updated.budget and _mentions_budget(text):
        updated.budget = amount
        changed = True

    before_seat = (updated.seat_style, updated.ac)
    _parse_seat(updated, text, partial_ok=True)
    if (updated.seat_style, updated.ac) != before_seat:
        changed = True

    priority = _priority_value(text)
    if priority and priority != updated.priority:
        updated.priority = priority
        changed = True

    if re.search(r"\brelaxed\b", text.lower()) and updated.pace != "relaxed":
        updated.pace = "relaxed"
        changed = True
    if re.search(r"\bpacked\b", text.lower()) and updated.pace != "packed":
        updated.pace = "packed"
        changed = True

    if re.search(r"\b(add|include|want|prefer|love|also)\b", text.lower()):
        for interest in _interest_hits(text):
            if interest not in updated.interests:
                updated.interests.append(interest)
                changed = True

    before_avoids = list(updated.avoids)
    if _followup_avoids(updated, text):
        changed = changed or updated.avoids != before_avoids
    return updated, changed


def extract_cities(text: str, known_cities: list[str]) -> list[str]:
    canonical = {city.lower(): city for city in known_cities}
    lookup = dict(canonical)
    for alias, target in ALIASES.items():
        if target in canonical:
            lookup[alias] = canonical[target]
    lowered = text.lower()
    occupied = [False] * len(lowered)
    found: list[tuple[int, str]] = []
    for alias in sorted(lookup, key=len, reverse=True):
        start = 0
        while True:
            index = lowered.find(alias, start)
            if index < 0:
                break
            end = index + len(alias)
            before_ok = index == 0 or not lowered[index - 1].isalnum()
            after_ok = end == len(lowered) or not lowered[end].isalnum()
            if before_ok and after_ok and not any(occupied[index:end]):
                for cursor in range(index, end):
                    occupied[cursor] = True
                found.append((index, lookup[alias]))
            start = index + 1
    found.sort()
    ordered: list[str] = []
    for _, city in found:
        if not ordered or ordered[-1] != city:
            ordered.append(city)
    return ordered


def _parse_route(profile: TravelerProfile, text: str, known_cities: list[str]) -> str | None:
    found = extract_cities(text, known_cities)
    if len(found) < 2:
        names = ", ".join(known_cities)
        return f"I need at least two cities from the sample network: {names}."
    if len(found) > 6:
        return "Tell me six cities at most. The start city stays fixed and I will order the rest."
    profile.cities = found
    profile.origin = found[0]
    profile.destination = found[-1]
    return None


def _parse_date(profile: TravelerProfile, text: str, today: date) -> str | None:
    lowered = text.lower().strip()
    flexible_word = bool(re.search(r"flexible|any day|whenever", lowered))
    either_side = "either side" in lowered
    found = _explicit_date(text, today)
    if found is None and (flexible_word or either_side):
        profile.travel_date = None
        profile.date_flexible = True
        return None
    if found is None:
        return "Give me a start date, or say the dates are flexible."
    profile.travel_date = found.isoformat()
    profile.date_flexible = flexible_word or either_side
    return None


def _explicit_date(text: str, today: date) -> date | None:
    lowered = text.lower()
    if "next friday" in lowered:
        return _upcoming(today, 4, allow_today=False)
    if "this weekend" in lowered:
        if today.weekday() >= 5:
            return today
        return _upcoming(today, 5, allow_today=True)
    cleaned = text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if match:
        try:
            return datetime.strptime(" ".join(match.groups()), "%d %B %Y").date()
        except ValueError:
            try:
                return datetime.strptime(" ".join(match.groups()), "%d %b %Y").date()
            except ValueError:
                return None
    return None


def _upcoming(today: date, weekday: int, allow_today: bool) -> date:
    ahead = (weekday - today.weekday()) % 7
    if ahead == 0 and not allow_today:
        ahead = 7
    return today + timedelta(days=ahead)


def _parse_budget(profile: TravelerProfile, text: str) -> str | None:
    amount = _budget_amount(text)
    if amount is None:
        return "Tell me the bus budget in rupees, for example 3000."
    profile.budget = amount
    return None


def _budget_amount(text: str) -> int | None:
    match = re.search(r"(\d[\d,]*)", text)
    if not match:
        return None
    amount = int(match.group(1).replace(",", ""))
    if amount < 100 or amount > 100000:
        return None
    return amount


def _mentions_budget(text: str) -> bool:
    return bool(re.search(r"\b(budget|rupee|rupees|rs|inr|under|around)\b|₹|up to", text.lower()))


def _parse_seat(profile: TravelerProfile, text: str, partial_ok: bool = False) -> str | None:
    lowered = text.lower().replace("–", "-")
    if "non-ac is fine" in lowered or "non ac is fine" in lowered:
        profile.ac = "any"
        profile.seat_style = profile.seat_style or "any"
    elif "no preference" in lowered:
        profile.seat_style = "any"
    elif "any ac" in lowered:
        profile.seat_style = "any"
        profile.ac = "ac"
    if re.search(r"\b(night|sleeper|overnight)\b", lowered):
        profile.seat_style = "night_sleeper"
    elif re.search(r"\b(day seater|daytime|seater)\b", lowered) or lowered.strip() == "day":
        profile.seat_style = "day_seater"
    if re.search(r"\bac only\b|avoid non-ac|avoid non ac|no non-ac|no non ac", lowered):
        profile.ac = "ac"
        _add(profile.avoids, "non_ac")
    elif profile.ac is None and re.search(r"\bnon[-\s]?ac\b", lowered):
        profile.ac = "non_ac"
    elif profile.ac is None and re.search(r"\bac\b", lowered):
        profile.ac = "ac"
    if profile.seat_style and profile.ac:
        return None
    if partial_ok and (profile.seat_style or profile.ac):
        return None
    if profile.seat_style or profile.ac:
        return None
    return "Choose a night AC sleeper, a day AC seater, any AC bus, or say non-AC is fine."


def _parse_priority(profile: TravelerProfile, text: str) -> str | None:
    priority = _priority_value(text)
    if not priority:
        return "Tell me whether to optimize for cheapest, fastest, or most comfortable."
    profile.priority = priority
    return None


def _priority_value(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\bcheap", lowered):
        return "cheapest"
    if re.search(r"\b(fast|faster|fastest|quickest)\b", lowered):
        return "fastest"
    if re.search(r"\bcomfort", lowered):
        return "comfortable"
    return None


def _parse_style(profile: TravelerProfile, text: str) -> str | None:
    before = (profile.pace, tuple(profile.interests), profile.avoids_confirmed)
    lowered = text.lower()
    if re.search(r"\b(relaxed|slow|easy)\b", lowered):
        profile.pace = "relaxed"
    if re.search(r"\b(packed|busy)\b", lowered):
        profile.pace = "packed"
    hits = _interest_hits(lowered)
    if "everything" in lowered:
        hits = list(INTERESTS)
    for interest in hits:
        if interest not in profile.interests:
            profile.interests.append(interest)
    if _avoid_language(lowered) or re.search(r"nothing|no avoid", lowered):
        _parse_avoids(profile, text)
    if (profile.pace, tuple(profile.interests), profile.avoids_confirmed) == before and not hits:
        return (
            "Tell me a pace, relaxed or packed, and at least one interest: "
            "heritage, food, nature, or shopping."
        )
    return None


def _parse_avoids(profile: TravelerProfile, text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\b(nothing|none|no restrictions)\b|no avoid", lowered):
        profile.avoids = []
        profile.avoids_confirmed = True
        return None
    found = _mark_avoids(profile, lowered)
    if not found:
        return "Say nothing to avoid, or mention early departures, long layovers, or non-AC buses."
    profile.avoids_confirmed = True
    return None


def _followup_avoids(profile: TravelerProfile, text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\b(nothing to avoid|no avoids|no restrictions)\b", lowered):
        profile.avoids = []
        profile.avoids_confirmed = True
        return True
    if not _avoid_language(lowered):
        return False
    _mark_avoids(profile, lowered)
    profile.avoids_confirmed = True
    return True


def _avoid_language(lowered: str) -> bool:
    return bool(
        re.search(
            r"\bearly\b|6\s*a\.?m|before 8|morning bus|layover|ac only|non[-\s]?ac|hate .*morning",
            lowered,
        )
    )


def _mark_avoids(profile: TravelerProfile, lowered: str) -> bool:
    found = False
    if re.search(r"\bearly\b|6\s*a\.?m|before 8|morning bus|hate .*morning|no morning", lowered):
        _add(profile.avoids, "early_departures")
        found = True
    if "layover" in lowered:
        _add(profile.avoids, "long_layovers")
        found = True
    if re.search(r"\bac only\b|non[-\s]?ac", lowered):
        _add(profile.avoids, "non_ac")
        profile.ac = "ac"
        found = True
    return found


def _interest_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    words = {
        "heritage": ("heritage", "history", "fort", "temple", "culture"),
        "food": ("food", "eat", "cuisine"),
        "nature": ("nature", "park", "beach", "lake", "garden"),
        "shopping": ("shopping", "market", "bazaar"),
    }
    for interest, tokens in words.items():
        if any(re.search(rf"\b{token}\b", lowered) for token in tokens):
            hits.append(interest)
    return hits


def _add(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _avoid_label(value: str) -> str:
    return {
        "early_departures": "early departures",
        "long_layovers": "long layovers",
        "non_ac": "non-AC buses",
    }.get(value, value)