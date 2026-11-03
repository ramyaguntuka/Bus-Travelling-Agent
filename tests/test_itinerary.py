from src.catalog import load_places
from src.itinerary import draft_itinerary, selected_place_names
from src.profile import TravelerProfile
from src.router import Bus, ScoredRoute


def test_itinerary_uses_only_the_arrival_city_catalog():
    leg = Bus(
        id="da-night",
        origin="Delhi",
        destination="Agra",
        operator="Fort Night Bus",
        depart="22:30",
        arrive="02:00",
        duration_min=210,
        fare=700,
        seat_type="sleeper",
        ac=True,
        comfort=4,
    )
    route = ScoredRoute(
        legs=[leg],
        score=0,
        total_fare=700,
        travel_minutes=210,
        ride_minutes=210,
        transfers=0,
        cities=["Delhi", "Agra"],
        reasons=["night sleeper"],
        relaxed_filters=False,
    )
    profile = TravelerProfile(
        cities=["Delhi", "Agra"],
        travel_date="2026-11-06",
        pace="relaxed",
        interests=["heritage"],
        budget=3000,
        priority="cheapest",
    )
    places = load_places()
    text = draft_itinerary(route, profile, places)
    assert "22:30" in text
    assert "Taj Mahal" in text
    assert "Amber Fort" not in text
    assert "Taj Mahal" in selected_place_names(route, profile, places)