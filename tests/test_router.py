from src.catalog import load_buses
from src.profile import TravelerProfile
from src.router import Bus, rank_routes, rank_tour


def bus(bus_id, origin, destination, depart, arrive, duration, fare, seat, ac=True, comfort=3):
    return Bus(
        id=bus_id,
        origin=origin,
        destination=destination,
        operator="Sample",
        depart=depart,
        arrive=arrive,
        duration_min=duration,
        fare=fare,
        seat_type=seat,
        ac=ac,
        comfort=comfort,
    )


def profile(**kwargs) -> TravelerProfile:
    base = dict(seat_style="any", ac="any", priority="cheapest", avoids=[], budget=None)
    base.update(kwargs)
    return TravelerProfile(**base)


def test_budget_ranks_cheaper_above_faster():
    buses = [
        bus("cheap", "A", "B", "22:00", "08:00", 600, 500, "sleeper", comfort=3),
        bus("fast", "A", "B", "22:00", "01:00", 180, 2000, "sleeper", comfort=4),
    ]
    ranked = rank_routes(buses, "A", "B", profile(priority="cheapest"))
    assert ranked[0].legs[0].id == "cheap"
    assert ranked[0].total_fare == 500


def test_night_sleeper_filters_early_bus():
    buses = [
        bus("early", "A", "B", "06:00", "12:00", 360, 400, "seater"),
        bus("night", "A", "B", "22:00", "04:00", 360, 700, "sleeper"),
    ]
    ranked = rank_routes(buses, "A", "B", profile(priority="fastest", seat_style="night_sleeper"))
    ids = [leg.id for route in ranked for leg in route.legs]
    assert "early" not in ids
    assert ranked[0].legs[0].id == "night"
    assert ranked[0].relaxed_filters is False


def test_night_sleeper_keeps_only_bus_when_nothing_else_fits():
    buses = [bus("early", "A", "B", "06:00", "12:00", 360, 400, "seater")]
    ranked = rank_routes(buses, "A", "B", profile(seat_style="night_sleeper"))
    assert ranked[0].legs[0].id == "early"
    assert ranked[0].relaxed_filters is True


def test_two_city_path_returns_expected_legs():
    buses = [
        bus("ab", "A", "B", "09:00", "12:00", 180, 300, "seater"),
        bus("bc", "B", "C", "13:00", "16:00", 180, 300, "seater"),
    ]
    ranked = rank_routes(buses, "A", "C", profile())
    assert [leg.id for leg in ranked[0].legs] == ["ab", "bc"]
    assert ranked[0].transfers == 1
    assert ranked[0].total_fare == 600


def test_tour_keeps_start_city_and_prefers_cheaper_order():
    buses = [
        bus("ab", "A", "B", "09:00", "12:00", 180, 100, "seater"),
        bus("bc", "B", "C", "14:00", "17:00", 180, 100, "seater"),
        bus("ac", "A", "C", "09:00", "18:00", 540, 500, "seater"),
        bus("cb", "C", "B", "09:00", "18:00", 540, 500, "seater"),
    ]
    ranked = rank_tour(buses, ["A", "C", "B"], profile(priority="cheapest"))
    assert [leg.id for leg in ranked[0].legs] == ["ab", "bc"]
    assert ranked[0].cities[0] == "A"


def test_sample_network_delhi_jaipur_cheapest():
    ranked = rank_routes(load_buses(), "Delhi", "Jaipur", profile(priority="cheapest", budget=3000))
    assert ranked[0].legs[0].id == "dj-cheap"
    assert ranked[0].total_fare < ranked[1].total_fare