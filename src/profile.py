"""Structured traveler answers. The route ranker reads these slots, not free text."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass
class TravelerProfile:
    origin: str | None = None
    destination: str | None = None
    cities: list[str] = field(default_factory=list)
    travel_date: str | None = None
    date_flexible: bool = False
    budget: int | None = None
    seat_style: str | None = None
    ac: str | None = None
    priority: str | None = None
    pace: str | None = None
    interests: list[str] = field(default_factory=list)
    avoids: list[str] = field(default_factory=list)
    avoids_confirmed: bool = False

    def missing_step(self) -> str | None:
        if len(self.cities) < 2:
            return "route"
        if self.travel_date is None and not self.date_flexible:
            return "date"
        if self.budget is None:
            return "budget"
        if self.seat_style is None or self.ac is None:
            return "seat"
        if self.priority is None:
            return "priority"
        if self.pace is None or not self.interests:
            return "style"
        if not self.avoids_confirmed:
            return "avoids"
        return None

    def ready(self) -> bool:
        return self.missing_step() is None

    def clone(self) -> "TravelerProfile":
        return TravelerProfile.from_dict(self.to_dict())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict | None) -> "TravelerProfile":
        raw = raw or {}
        known = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in raw.items() if key in known})