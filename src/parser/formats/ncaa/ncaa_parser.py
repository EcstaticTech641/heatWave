"""
NCAA / Collegiate Psych Sheet Parser Engine (Experimental)

WARNING: This module contains experimental parsing logic for NCAA/collegiate multi-column
championship psych sheets. It is inactive for primary USA Swimming age-group meets in v1.1.4.

To enable during testing, set environment variable: HEATWAVE_NCAA=1
"""
import re
from typing import List
from src.models.schemas import Event, Swimmer, Entry, RelayEntry
from ...extractor import BasePsychSheetParser, normalize_seed_time, normalize_age_group


# NCAA / Championship Regular Expressions
NCAA_EVENT_HEADER_RE = (
    r"Event\s+(\d+)(X)?\s+"
    r"(Girls|Boys|Women|Men|Mixed)\s+"
    r"(?:"
        r"(.*?)\s*(\d+)\s+Yard\s+(.+?)(?:\s+Relay)?(?:\s+(?:NCAA|D2|D3|Division|Official).*|)?\s*$"   # standard swim event
        r"|"
        r"(\d+(?:\.\d+)?)\s*(?:mtr|m)\s+(Diving)(?:\s+(?:NCAA|D2|D3|Division|Official).*|)?\s*$"        # diving event: "3 mtr Diving..."
    r")"
)
NCAA_ATHLETE_RE = r"^\s*(\d+)\s+([A-Za-z\s,\.'\-]+?)\s+(FR|SO|JR|SR|GR|GS|[0-9]{1,2})\s+([A-Za-z0-9\-]+)\s+([Xx]?\d{1,2}:\d{2}\.\d{2}|[Xx]?\d{2}\.\d{2}|[Xx]?NT)\s*([A-Z\*]*)\s*$"
NCAA_DIVE_RE = r"^\s*(\d+)\s+([A-Za-z\s,\.'\-]+?)\s+(FR|SO|JR|SR|GR|GS|[0-9]{1,2})\s+([A-Za-z0-9\-]+)\s+([Xx]?\d+\.\d{2}|NP|NT)\s*$"
NCAA_RELAY_RE = r"^\s*(\d+)\s+([A-Za-z0-9\-\.\s]+?)\s+([A-Z])\s+([Xx]?\d{1,2}:\d{2}\.\d{2}|[Xx]?NT)\s*([A-Z\*]*)\s*$"

NCAA_ANCHOR_INDIVIDUAL_RE = r"\bYr\b.*\bName\b.*\bSchool\b|\bName\b.*\bYr\b.*\bSchool\b"
NCAA_ANCHOR_RELAY_RE = r"\bTeam\b.*\bRelay\b.*\bSeed\b"
NCAA_ANCHOR_DIVE_RE = r"\bName\b.*\bYr\b.*\bSchool\b"


def parse_event_header_extended(line: str) -> dict | None:
    """Parses event header lines for NCAA/collegiate meets with relay, diving, and exhibition support."""
    match = re.match(NCAA_EVENT_HEADER_RE, line.strip())
    if not match:
        return None

    event_num = int(match.group(1))
    is_exhibition = match.group(2) == "X"
    gender = match.group(3)

    if match.group(8):  # diving branch matched
        dive_height = match.group(7)
        return {
            "number": event_num,
            "event_label": f"{match.group(1)}{match.group(2) or ''}",
            "name": f"{match.group(7)} mtr Diving",
            "gender": gender,
            "distance": 0,
            "stroke": f"{dive_height}m Diving",
            "is_exhibition": is_exhibition,
            "is_relay": False,
            "is_diving": True,
        }

    age_group = normalize_age_group(match.group(4)) if match.group(4) else ""
    distance = int(match.group(5))
    stroke = match.group(6)
    is_relay = "Relay" in line
    event_name = f"{age_group} {distance}Y {stroke}".strip()

    return {
        "number": event_num,
        "event_label": f"{match.group(1)}{match.group(2) or ''}",
        "name": event_name,
        "gender": gender,
        "distance": distance,
        "stroke": stroke,
        "is_exhibition": is_exhibition,
        "is_relay": is_relay,
        "is_diving": False,
    }


class NCAACollegeParser(BasePsychSheetParser):
    """Strategy for collegiate/championship sheets — handles individual,
    relay, and diving events via structural anchoring."""

    def parse(self, raw_text: str) -> List[Event]:
        # Normalize curly apostrophes/quotes from PDF extraction to ASCII
        raw_text = (
            raw_text
            .replace('\u2019', "'")
            .replace('\u2018', "'")
            .replace('\u201c', '"')
            .replace('\u201d', '"')
        )

        events: List[Event] = []
        current_event: Event | None = None
        parsing_entries = False
        entry_mode: str | None = None   # "individual" | "relay" | "diving"

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        for line in lines:
            header_info = parse_event_header_extended(line)
            if header_info:
                if current_event:
                    events.append(current_event)

                current_event = Event(
                    number=header_info["number"],
                    event_label=header_info["event_label"],
                    name=header_info.get("name", header_info["stroke"]),
                    gender=header_info["gender"],
                    distance=header_info["distance"],
                    stroke=header_info["stroke"],
                    is_exhibition=header_info["is_exhibition"],
                    entries=[],
                )
                parsing_entries = False
                entry_mode = (
                    "diving" if header_info["is_diving"]
                    else "relay" if header_info["is_relay"]
                    else "individual"
                )
                continue

            if current_event and not parsing_entries:
                if entry_mode == "relay" and re.search(NCAA_ANCHOR_RELAY_RE, line):
                    parsing_entries = True
                elif entry_mode in ("individual", "diving") and re.search(NCAA_ANCHOR_INDIVIDUAL_RE, line):
                    parsing_entries = True
                continue

            if current_event and parsing_entries:
                if entry_mode == "individual":
                    m = re.match(NCAA_ATHLETE_RE, line)
                    if m:
                        swimmer = Swimmer(name=m.group(2).strip(), year=m.group(3).strip(), team_code=m.group(4).strip())
                        entry = Entry(place=int(m.group(1)), swimmer=swimmer, seed_time=normalize_seed_time(m.group(5)))
                        current_event.entries.append(entry)

                elif entry_mode == "diving":
                    m = re.match(NCAA_DIVE_RE, line)
                    if m:
                        swimmer = Swimmer(name=m.group(2).strip(), year=m.group(3).strip(), team_code=m.group(4).strip())
                        entry = Entry(place=int(m.group(1)), swimmer=swimmer, seed_time=m.group(5))
                        current_event.entries.append(entry)

                elif entry_mode == "relay":
                    m = re.match(NCAA_RELAY_RE, line)
                    if m:
                        team_label = f"{m.group(2).strip()} {m.group(3).strip()}"
                        relay = RelayEntry(place=int(m.group(1)), team_name=team_label, seed_time=normalize_seed_time(m.group(4)))
                        current_event.entries.append(relay)

        if current_event:
            events.append(current_event)

        return events
