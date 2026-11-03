from datetime import date

from src.interview import apply_answer, apply_followup, extract_cities
from src.profile import TravelerProfile

CITIES = [
    "Delhi",
    "Agra",
    "Jaipur",
    "Udaipur",
    "Mumbai",
    "Goa",
    "Bengaluru",
    "Chennai",
]


def test_extracts_aliases_in_order():
    assert extract_cities("Bangalore to Madras", CITIES) == ["Bengaluru", "Chennai"]
    assert extract_cities("Delhi, Jaipur, Udaipur", CITIES) == ["Delhi", "Jaipur", "Udaipur"]


def test_interview_fills_every_slot():
    profile = TravelerProfile()
    today = date(2026, 11, 3)
    answers = [
        "Delhi to Jaipur",
        "Next Friday",
        "Around ₹3,000",
        "Night AC sleeper",
        "Cheapest",
        "Relaxed, heritage and food",
        "Nothing to avoid",
    ]
    for text in answers:
        profile, error = apply_answer(profile, text, CITIES, today=today)
        assert error is None, text
    assert profile.ready()
    assert profile.cities == ["Delhi", "Jaipur"]
    assert profile.travel_date == "2026-11-06"
    assert profile.budget == 3000
    assert profile.seat_style == "night_sleeper"
    assert profile.ac == "ac"
    assert profile.priority == "cheapest"
    assert profile.pace == "relaxed"
    assert profile.interests == ["heritage", "food"]
    assert profile.avoids == []


def test_followup_early_bus_sets_avoid_without_resetting_route():
    profile = TravelerProfile(
        origin="Delhi",
        destination="Jaipur",
        cities=["Delhi", "Jaipur"],
        date_flexible=True,
        budget=3000,
        seat_style="night_sleeper",
        ac="ac",
        priority="cheapest",
        pace="relaxed",
        interests=["heritage"],
        avoids_confirmed=True,
    )
    updated, changed = apply_followup(profile, "I hate 6 a.m. buses", CITIES)
    assert changed
    assert updated.cities == ["Delhi", "Jaipur"]
    assert "early_departures" in updated.avoids
    assert updated.budget == 3000

    unchanged, changed = apply_followup(updated, "What time do I arrive?", CITIES)
    assert changed is False
    assert unchanged.avoids == updated.avoids