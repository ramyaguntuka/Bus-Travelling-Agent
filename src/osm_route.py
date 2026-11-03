"""OpenStreetMap route line for the recommended bus stops."""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

# City centers in the sample network. Latitude, longitude.
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "Delhi": (28.6139, 77.2090),
    "Agra": (27.1767, 78.0081),
    "Jaipur": (26.9124, 75.7873),
    "Udaipur": (24.5854, 73.7125),
    "Ahmedabad": (23.0225, 72.5714),
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Goa": (15.4909, 73.8278),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Kochi": (9.9312, 76.2673),
}

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{path}?overview=full&geometries=geojson"


def stop_coordinates(cities: list[str]) -> list[tuple[str, float, float]]:
    return [
        (city, *CITY_COORDINATES[city])
        for city in cities
        if city in CITY_COORDINATES
    ]


def route_geometry(cities: list[str], fetch=None) -> tuple[list[list[float]], str]:
    """Return the map line as [latitude, longitude] pairs and where it came from.

    `osrm` means the line follows OpenStreetMap roads. `straight` means the
    routing service was unavailable and the stops are connected directly.
    """
    stops = stop_coordinates(cities)
    direct = [[lat, lon] for _city, lat, lon in stops]
    if len(direct) < 2:
        return direct, "straight"
    loader = fetch or _fetch_osrm
    try:
        line = loader(stops)
    except (OSError, URLError, TimeoutError, ValueError, KeyError, IndexError, json.JSONDecodeError):
        return direct, "straight"
    if len(line) < 2:
        return direct, "straight"
    return line, "osrm"


def _fetch_osrm(stops: list[tuple[str, float, float]]) -> list[list[float]]:
    path = ";".join(f"{lon},{lat}" for _city, lat, lon in stops)
    request = Request(
        OSRM_URL.format(path=path),
        headers={"User-Agent": "TravellingAgent/1.0 (personal bus planner)"},
    )
    with urlopen(request, timeout=8) as response:
        payload = json.load(response)
    coordinates = payload["routes"][0]["geometry"]["coordinates"]
    return [[lat, lon] for lon, lat in coordinates]


def build_map(cities: list[str], line: list[list[float]]):
    import folium

    stops = stop_coordinates(cities)
    points = line or [[lat, lon] for _city, lat, lon in stops]
    center = points[len(points) // 2]
    route_map = folium.Map(location=center, tiles="OpenStreetMap", zoom_start=6, control_scale=True)
    folium.PolyLine(points, color="#c2410c", weight=5, opacity=0.9).add_to(route_map)
    for index, (city, lat, lon) in enumerate(stops, start=1):
        folium.Marker(
            [lat, lon],
            tooltip=f"{index}. {city}",
            popup=folium.Popup(f"<b>{index}. {city}</b>", max_width=180),
            icon=folium.DivIcon(
                html=(
                    "<div style='background:#9a3412;color:white;border-radius:50%;"
                    "width:26px;height:26px;line-height:26px;text-align:center;"
                    "font-weight:700;font-size:13px;border:2px solid white;'>"
                    f"{index}</div>"
                ),
                icon_size=(26, 26),
                icon_anchor=(13, 13),
            ),
        ).add_to(route_map)
    route_map.fit_bounds(points, padding=(24, 24))
    return route_map