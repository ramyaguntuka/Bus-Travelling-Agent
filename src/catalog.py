"""Load the sample bus graph and the sightseeing catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.router import Bus

ROOT = Path(__file__).resolve().parents[1]
BUSES_PATH = ROOT / "data" / "buses.json"
PLACES_PATH = ROOT / "data" / "places.json"


@dataclass(frozen=True)
class Place:
    name: str
    hours: float
    tags: tuple[str, ...]
    slot: str


def load_buses(path: Path | None = None) -> list[Bus]:
    payload = json.loads((path or BUSES_PATH).read_text(encoding="utf-8"))
    return [Bus(**item) for item in payload["buses"]]


def load_places(path: Path | None = None) -> dict[str, list[Place]]:
    payload = json.loads((path or PLACES_PATH).read_text(encoding="utf-8"))
    catalog: dict[str, list[Place]] = {}
    for city, places in payload.items():
        catalog[city] = [
            Place(
                name=place["name"],
                hours=float(place["hours"]),
                tags=tuple(place["tags"]),
                slot=place.get("slot", "any"),
            )
            for place in places
        ]
    return catalog


def known_cities(buses: list[Bus]) -> list[str]:
    names = {bus.origin for bus in buses} | {bus.destination for bus in buses}
    return sorted(names)