from src.osm_route import route_geometry, stop_coordinates


def test_stop_coordinates_follow_city_order():
    stops = stop_coordinates(["Jaipur", "Delhi", "Missing"])
    assert [city for city, _lat, _lon in stops] == ["Jaipur", "Delhi"]
    assert stops[1][1] == 28.6139


def test_route_geometry_uses_openstreetmap_roads_when_the_service_replies():
    line, source = route_geometry(
        ["Delhi", "Jaipur"],
        fetch=lambda stops: [[28.6, 77.2], [27.4, 76.5], [26.9, 75.8]],
    )
    assert source == "osrm"
    assert line[0] == [28.6, 77.2]
    assert line[-1] == [26.9, 75.8]


def test_route_geometry_falls_back_to_a_direct_line():
    def fail(_stops):
        raise TimeoutError("routing unavailable")

    line, source = route_geometry(["Delhi", "Jaipur"], fetch=fail)
    assert source == "straight"
    assert line[0][0] == 28.6139
    assert line[-1][0] == 26.9124