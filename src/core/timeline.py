"""
Timeline estimation for heatWave.

Computes estimated start times and durations for every heat across a meet,
based on the slowest timed seed in each heat plus a configurable between-heat
gap (to account for check-in, clearing the deck, and the start signal).

NT (no-time) heats fall back to a default duration:
  - Events longer than 400 yards: 5 minutes
  - All other events:             2 minutes

Wall-clock times are computed from a user-supplied session start heat number
and a meet start time string (e.g. "8:00 AM").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from src.models.schemas import HeatSheet, Entry, RelayEntry, SessionConfig


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class HeatTimeline:
    """Timing data for a single heat."""
    heat_number: int
    est_start_minutes: float       # cumulative minutes from this session's clock-zero
    est_duration_minutes: float    # derived from the slowest timed seed
    est_start_wall: str            # wall-clock string, e.g. "9:14 AM"
    session_name: str = ""         # populated when sessions are defined


@dataclass
class EventTimeline:
    """Timing data for all heats in one event."""
    event_number: int
    event_name: str
    session_name: str = ""         # populated when sessions are defined
    heats: List[HeatTimeline] = field(default_factory=list)

    @property
    def est_start_wall(self) -> str:
        """Wall-clock start of the first heat in this event."""
        if self.heats:
            return self.heats[0].est_start_wall
        return ""

    @property
    def est_end_wall(self) -> str:
        """Wall-clock end of the last heat in this event."""
        if self.heats:
            last = self.heats[-1]
            return last.est_start_wall  # callers that want end use last heat start + dur
        return ""


@dataclass
class MeetTimeline:
    """Complete timeline for a meet — single or multi-session."""
    events: List[EventTimeline] = field(default_factory=list)
    total_duration_minutes: float = 0.0   # sum of all session active times, gaps excluded
    meet_start_wall: str = "8:00 AM"      # first session's start time
    sessions: List[SessionConfig] = field(default_factory=list)

    def format_total(self) -> str:
        """Return total duration as a human-readable string, e.g. '2h 14m'."""
        return _format_duration(self.total_duration_minutes)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_duration(minutes: float) -> str:
    """Convert a float number of minutes to '1h 14m' style string."""
    total_m = int(round(minutes))
    h, m = divmod(total_m, 60)
    if h > 0 and m > 0:
        return f"{h}h {m}m"
    if h > 0:
        return f"{h}h"
    return f"{m}m"


def _parse_meet_start(start_time_str: str) -> datetime:
    """
    Parse a user-supplied start time string into a datetime (date is irrelevant).
    Tries several common formats: "8:00 AM", "08:00", "8:00", "800".
    Falls back to 8:00 AM on failure.
    """
    formats = ["%I:%M %p", "%I:%M%p", "%H:%M", "%I %p", "%I%p"]
    cleaned = start_time_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # fallback
    return datetime.strptime("8:00 AM", "%I:%M %p")


def _wall_clock(base: datetime, offset_minutes: float) -> str:
    """Return a formatted wall-clock string for base + offset_minutes."""
    dt = base + timedelta(minutes=offset_minutes)
    # Use "%-I" on Unix, but strftime %I is fine on Windows (no leading zero stripping needed)
    return dt.strftime("%I:%M %p").lstrip("0") or "12:00 AM"


def _seed_to_seconds(seed_time: str) -> Optional[float]:
    """
    Convert a seed time string to seconds.
    Returns None for NT or unparseable values.
    """
    if seed_time.upper() == "NT" or not seed_time:
        return None
    try:
        parts = seed_time.split(":")
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60.0 + seconds
    except (IndexError, ValueError):
        return None


def _nt_fallback_minutes(event_distance: int) -> float:
    """
    Return a fallback heat duration in minutes for NT-only heats.
    Events > 400 yards → 5 minutes; otherwise → 2 minutes.
    """
    return 5.0 if event_distance > 400 else 2.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def estimate_meet_timeline(
    heat_sheets: List[HeatSheet],
    gap_minutes: float = 2.0,
    meet_start_time: str = "8:00 AM",
    start_heat_number: int = 1,
    sessions: Optional[List[SessionConfig]] = None,
) -> MeetTimeline:
    """
    Compute estimated start times and durations for every heat across a meet.

    Single-session behavior (sessions=None or []):
        Identical to the previous implementation — one clock running from
        meet_start_time through all events.

    Multi-session behavior:
        Sessions are sorted by start_event_num. When the engine crosses a
        session boundary, base_dt resets to the new session's start_time and
        cursor_minutes resets to 0.0. Heat numbers are never reset — they
        thread globally across all sessions from the upstream seeder.

        Inter-session gaps (lunch breaks, warmup, etc.) are implicit: they are
        the delta between Session N's last calculated wall-clock time and
        Session N+1's user-defined start_time. The engine does not model them.

    Args:
        heat_sheets:       Ordered list of HeatSheet objects (one per event).
        gap_minutes:       Minutes added between heats (check-in buffer).
        meet_start_time:   Fallback/single-session start time, e.g. "8:00 AM".
        start_heat_number: Reserved for future partial-meet support (unused in
                           current multi-session path).
        sessions:          Optional list of SessionConfig. If None or empty,
                           single-session mode — existing behavior is preserved.

    Returns:
        MeetTimeline with per-event, per-heat timing data tagged by session.
        total_duration_minutes reflects the sum of all session active times,
        excluding inter-session gaps.
    """
    # --- Normalize sessions ---
    sessions_sorted: List[SessionConfig] = []
    if sessions:
        sessions_sorted = sorted(sessions, key=lambda s: s.start_event_num)

    def _get_session_for_event(event_num: int) -> Optional[SessionConfig]:
        """Return the SessionConfig whose boundary covers this event, or None."""
        matched: Optional[SessionConfig] = None
        for s in sessions_sorted:
            if s.start_event_num <= event_num:
                matched = s
            else:
                break
        return matched

    # --- Clock state ---
    base_dt: datetime = _parse_meet_start(
        sessions_sorted[0].start_time if sessions_sorted else meet_start_time
    )
    cursor_minutes: float = 0.0
    current_session_name: str = ""

    # Accumulates active time from completed sessions (trailing gap already removed).
    # Used to compute total_duration_minutes correctly across resets.
    completed_session_minutes: float = 0.0

    timeline = MeetTimeline(
        meet_start_wall=sessions_sorted[0].start_time if sessions_sorted else meet_start_time,
        sessions=sessions_sorted,
    )

    for heat_sheet in heat_sheets:
        event = heat_sheet.event

        # --- Session boundary detection ---
        session = _get_session_for_event(event.number) if sessions_sorted else None
        session_label = session.session_name if session else ""

        if session is not None and session.session_name != current_session_name:
            if current_session_name:
                # A previous session was active — save its active time before reset.
                # cursor_minutes currently ends with a trailing gap from the last heat;
                # subtract it so we only count actual race time + within-session gaps.
                completed_session_minutes += max(cursor_minutes - gap_minutes, 0.0)

            # Reset clock to this session's wall-clock origin
            base_dt = _parse_meet_start(session.start_time)
            cursor_minutes = 0.0
            current_session_name = session.session_name

        # --- Build EventTimeline ---
        event_tl = EventTimeline(
            event_number=event.number,
            event_name=f"Event {event.number}: {event.gender} {event.distance}Y {event.stroke}",
            session_name=session_label,
        )

        # Group assignments by heat number
        heats_map: dict[int, list] = {}
        for assignment in heat_sheet.assignments:
            heats_map.setdefault(assignment.heat, []).append(assignment)

        nt_fallback = _nt_fallback_minutes(event.distance)

        for heat_num in sorted(heats_map.keys()):
            assignments = heats_map[heat_num]

            # Find the slowest timed seed in this heat
            worst_seconds: Optional[float] = None
            for assignment in assignments:
                entry = assignment.entry
                seed_str = entry.seed_time if hasattr(entry, "seed_time") else "NT"
                secs = _seed_to_seconds(seed_str)
                if secs is not None:
                    if worst_seconds is None or secs > worst_seconds:
                        worst_seconds = secs

            heat_duration_minutes = (
                worst_seconds / 60.0 if worst_seconds is not None else nt_fallback
            )

            heat_tl = HeatTimeline(
                heat_number=heat_num,
                est_start_minutes=cursor_minutes,
                est_duration_minutes=heat_duration_minutes,
                est_start_wall=_wall_clock(base_dt, cursor_minutes),
                session_name=session_label,
            )
            event_tl.heats.append(heat_tl)

            cursor_minutes += heat_duration_minutes + gap_minutes

        timeline.events.append(event_tl)

    # --- Total duration ---
    # Remove the trailing gap appended after the final heat, then add to completed sessions.
    if timeline.events:
        last_event = timeline.events[-1]
        if last_event.heats:
            cursor_minutes -= gap_minutes

    timeline.total_duration_minutes = completed_session_minutes + cursor_minutes

    return timeline


def lookup_swimmer_schedule(
    swimmer_name_query: str,
    heat_sheets: List[HeatSheet],
    timeline: Optional[MeetTimeline] = None,
) -> List[dict]:
    """
    Find all individual heat assignments matching a partial swimmer name.

    Relay entries are excluded (no individual to search for).

    Args:
        swimmer_name_query: Partial first or last name (case-insensitive).
        heat_sheets:        List of generated HeatSheet objects.
        timeline:           Optional MeetTimeline for estimated start times.

    Returns:
        List of dicts, each representing one event entry for the swimmer:
        {
            "swimmer_name": str,
            "team_code":    str,
            "event_number": int,
            "event_name":   str,
            "heat":         int,
            "lane":         int,
            "seed_time":    str,
            "est_start":    str,   # wall-clock or "" if no timeline
        }
    """
    query = swimmer_name_query.strip().lower()
    results: List[dict] = []

    # Build a fast lookup from (event_number, heat_number) → HeatTimeline
    heat_time_map: dict[tuple[int, int], HeatTimeline] = {}
    if timeline:
        for event_tl in timeline.events:
            for heat_tl in event_tl.heats:
                heat_time_map[(event_tl.event_number, heat_tl.heat_number)] = heat_tl

    for heat_sheet in heat_sheets:
        event = heat_sheet.event
        event_label = f"Event {event.number}: {event.gender} {event.distance}Y {event.stroke}"

        for assignment in heat_sheet.assignments:
            entry = assignment.entry

            # Skip relay entries
            if not isinstance(entry, Entry):
                continue

            swimmer = entry.swimmer
            full_name = swimmer.name.lower()

            if query not in full_name:
                continue

            heat_tl = heat_time_map.get((event.number, assignment.heat))
            est_start = heat_tl.est_start_wall if heat_tl else ""

            results.append({
                "swimmer_name": swimmer.name,
                "team_code": swimmer.team_code,
                "event_number": event.number,
                "event_name": event_label,
                "heat": assignment.heat,
                "lane": assignment.lane,
                "seed_time": entry.seed_time,
                "est_start": est_start,
            })

    # Sort by event number then heat
    results.sort(key=lambda r: (r["event_number"], r["heat"]))
    return results


def get_unique_swimmers(heat_sheets: List[HeatSheet]) -> List[dict]:
    """
    Return a deduplicated list of individual swimmers across all events.

    Returns:
        List of dicts: {"name": str, "team_code": str, "event_count": int}
        Sorted alphabetically by name.
    """
    swimmer_events: dict[tuple[str, str], int] = {}

    for heat_sheet in heat_sheets:
        for assignment in heat_sheet.assignments:
            entry = assignment.entry
            if not isinstance(entry, Entry):
                continue
            key = (entry.swimmer.name, entry.swimmer.team_code)
            swimmer_events[key] = swimmer_events.get(key, 0) + 1

    result = [
        {"name": name, "team_code": team, "event_count": count}
        for (name, team), count in swimmer_events.items()
    ]
    result.sort(key=lambda s: s["name"].lower())
    return result
