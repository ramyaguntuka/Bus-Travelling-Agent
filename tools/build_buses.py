"""Write data/buses.json. Run once when the sample network changes."""

from __future__ import annotations

import json
from pathlib import Path


def minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def duration(depart: str, arrive: str, midnights: int) -> int:
    total = minutes(arrive) - minutes(depart) + 1440 * midnights
    if not 60 <= total <= 2000:
        raise ValueError(f"bad duration {depart}-{arrive} x{midnights} = {total}")
    return total


ROWS = [
    ("da-early", "Delhi", "Agra", "Yamuna Coach", "06:00", "09:30", 0, 450, "seater", True, 3),
    ("da-day", "Delhi", "Agra", "Yamuna Coach", "14:00", "17:15", 0, 550, "seater", True, 3),
    ("da-night", "Delhi", "Agra", "Fort Night Bus", "22:30", "02:00", 1, 700, "sleeper", True, 4),
    ("dj-early", "Delhi", "Jaipur", "Aravalli Travels", "06:00", "11:30", 0, 600, "seater", True, 3),
    ("dj-cheap", "Delhi", "Jaipur", "Aravalli Travels", "09:00", "15:30", 0, 380, "seater", False, 2),
    ("dj-volvo", "Delhi", "Jaipur", "Pink City Lines", "16:00", "21:00", 0, 1100, "seater", True, 5),
    ("dj-night", "Delhi", "Jaipur", "Pink City Lines", "23:00", "04:30", 1, 900, "sleeper", True, 5),
    ("aj-day", "Agra", "Jaipur", "Yamuna Coach", "08:00", "12:30", 0, 500, "seater", True, 3),
    ("aj-night", "Agra", "Jaipur", "Fort Night Bus", "21:00", "01:30", 1, 750, "sleeper", True, 4),
    ("ju-day", "Jaipur", "Udaipur", "Aravalli Travels", "07:00", "14:00", 0, 800, "seater", True, 3),
    ("ju-cheap", "Jaipur", "Udaipur", "Aravalli Travels", "10:00", "18:00", 0, 550, "seater", False, 2),
    ("ju-night", "Jaipur", "Udaipur", "Pink City Lines", "22:00", "05:00", 1, 1100, "sleeper", True, 5),
    ("ua-day", "Udaipur", "Ahmedabad", "Narmada Travels", "06:30", "12:00", 0, 700, "seater", True, 3),
    ("ua-night", "Udaipur", "Ahmedabad", "Narmada Travels", "21:30", "03:00", 1, 950, "sleeper", True, 4),
    ("am-day", "Ahmedabad", "Mumbai", "Narmada Travels", "07:00", "14:00", 0, 900, "seater", True, 3),
    ("am-cheap", "Ahmedabad", "Mumbai", "Sabarmati Lines", "08:00", "16:30", 0, 600, "seater", False, 2),
    ("am-night", "Ahmedabad", "Mumbai", "Fort Night Bus", "22:00", "05:30", 1, 1200, "sleeper", True, 5),
    ("dm-fast", "Delhi", "Mumbai", "Fort Night Bus", "18:00", "16:00", 1, 2500, "sleeper", True, 5),
    ("dm-cheap", "Delhi", "Mumbai", "Fort Night Bus", "20:00", "22:00", 1, 1400, "sleeper", False, 3),
    ("mp-day", "Mumbai", "Pune", "Sahyadri Bus", "07:00", "10:30", 0, 400, "seater", True, 3),
    ("mp-fast", "Mumbai", "Pune", "Sahyadri Bus", "14:00", "17:00", 0, 550, "seater", True, 4),
    ("mp-night", "Mumbai", "Pune", "Sahyadri Bus", "23:00", "02:15", 1, 500, "sleeper", True, 4),
    ("pg-day", "Pune", "Goa", "Coastal Express", "07:00", "16:00", 0, 1000, "seater", True, 3),
    ("pg-cheap", "Pune", "Goa", "Coastal Express", "08:00", "18:30", 0, 700, "seater", False, 2),
    ("pg-night", "Pune", "Goa", "Coastal Express", "20:00", "06:00", 1, 1200, "sleeper", True, 5),
    ("mg-day", "Mumbai", "Goa", "Coastal Express", "06:30", "16:00", 0, 1300, "seater", True, 3),
    ("mg-night", "Mumbai", "Goa", "Coastal Express", "19:00", "07:00", 1, 1500, "sleeper", True, 5),
    ("mg-cheap", "Mumbai", "Goa", "Coastal Express", "21:00", "10:00", 1, 900, "sleeper", False, 3),
    ("mb-night", "Mumbai", "Bengaluru", "Deccan Sleeper", "16:00", "14:00", 1, 2200, "sleeper", True, 4),
    ("mb-cheap", "Mumbai", "Bengaluru", "Deccan Sleeper", "18:00", "18:00", 1, 1400, "sleeper", False, 3),
    ("pb-night", "Pune", "Bengaluru", "Deccan Sleeper", "17:00", "10:00", 1, 1800, "sleeper", True, 4),
    ("pb-cheap", "Pune", "Bengaluru", "Deccan Sleeper", "19:00", "14:00", 1, 1100, "sleeper", False, 2),
    ("gb-night", "Goa", "Bengaluru", "Coastal Express", "18:00", "12:00", 1, 1900, "sleeper", True, 4),
    ("bh-day", "Bengaluru", "Hyderabad", "Deccan Sleeper", "07:00", "15:00", 0, 900, "seater", True, 3),
    ("bh-cheap", "Bengaluru", "Hyderabad", "Deccan Sleeper", "08:00", "17:00", 0, 600, "seater", False, 2),
    ("bh-night", "Bengaluru", "Hyderabad", "Deccan Sleeper", "22:00", "06:00", 1, 1100, "sleeper", True, 5),
    ("hc-day", "Hyderabad", "Chennai", "Charminar Coach", "06:00", "16:00", 0, 1100, "seater", True, 3),
    ("hc-night", "Hyderabad", "Chennai", "Charminar Coach", "21:00", "07:00", 1, 1300, "sleeper", True, 5),
    ("bc-fast", "Bengaluru", "Chennai", "Cauvery Lines", "07:00", "13:00", 0, 1200, "seater", True, 5),
    ("bc-cheap", "Bengaluru", "Chennai", "Cauvery Lines", "09:00", "16:30", 0, 650, "seater", False, 2),
    ("bc-night", "Bengaluru", "Chennai", "Cauvery Lines", "22:00", "05:00", 1, 1000, "sleeper", True, 4),
    ("bk-day", "Bengaluru", "Kochi", "Malabar Coach", "07:00", "16:00", 0, 1200, "seater", True, 3),
    ("bk-night", "Bengaluru", "Kochi", "Malabar Coach", "20:00", "06:00", 1, 1400, "sleeper", True, 5),
    ("ck-day", "Chennai", "Kochi", "Malabar Coach", "06:00", "18:00", 0, 1300, "seater", True, 3),
    ("ck-night", "Chennai", "Kochi", "Malabar Coach", "19:00", "07:00", 1, 1500, "sleeper", True, 4),
    ("hm-night", "Hyderabad", "Mumbai", "Charminar Coach", "17:00", "09:00", 1, 1800, "sleeper", True, 4),
    ("hm-cheap", "Hyderabad", "Mumbai", "Charminar Coach", "19:00", "13:00", 1, 1200, "sleeper", False, 3),
    ("dh-night", "Delhi", "Hyderabad", "Fort Night Bus", "18:00", "18:00", 1, 2800, "sleeper", True, 4),
    ("dh-cheap", "Delhi", "Hyderabad", "Fort Night Bus", "20:00", "22:00", 1, 1600, "sleeper", False, 3),
]


def bus_dict(row, bus_id=None):
    bus_id, origin, dest, operator, depart, arrive, midnights, fare, seat, ac, comfort = row
    return {
        "id": bus_id if bus_id is None else bus_id,
        "origin": origin,
        "destination": dest,
        "operator": operator,
        "depart": depart,
        "arrive": arrive,
        "duration_min": duration(depart, arrive, midnights),
        "fare": fare,
        "seat_type": seat,
        "ac": ac,
        "comfort": comfort,
    }


def main() -> None:
    buses = []
    seen = set()
    for row in ROWS:
        item = bus_dict(row)
        item["id"] = row[0]
        buses.append(item)
        seen.add((item["origin"], item["destination"], item["depart"], item["seat_type"], item["fare"]))
    mirrored = []
    for item in buses:
        key = (item["destination"], item["origin"], item["depart"], item["seat_type"], item["fare"])
        if key in seen:
            continue
        copy = dict(item)
        copy["id"] = item["id"] + "-r"
        copy["origin"], copy["destination"] = item["destination"], item["origin"]
        mirrored.append(copy)
        seen.add(key)
    buses.extend(mirrored)
    ids = [item["id"] for item in buses]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate bus ids")
    payload = {"buses": buses}
    path = Path(__file__).resolve().parents[1] / "data" / "buses.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {len(buses)} buses to {path}")


if __name__ == "__main__":
    main()