"""
HeatWave Core Controller Module
Provides HeatWaveController as the sole business logic controller for state mutations.
Zero UI (streamlit) or platform (win32) dependencies.
"""
from typing import Optional, Union, Dict
from src.models.schemas import ParseResult, Event, Entry, RelayEntry, HeatSheet
from src.parser.extractor import normalize_seed_time
from src.seeding.seeder import seed_event


class HeatWaveController:
    """Sole business logic controller for state mutations on ParseResult objects."""

    def __init__(self, parse_result: ParseResult):
        self.parse_result = parse_result

    def _find_event(self, event_id: str) -> Optional[Event]:
        target = str(event_id).strip().lower()
        for event in self.parse_result.events:
            if event.event_id.lower() == target or str(event.number) == target:
                return event
        return None

    def _find_entry(self, event: Event, entry_id: str) -> Optional[Union[Entry, RelayEntry]]:
        target = str(entry_id).strip().lower()
        for entry in event.entries:
            if str(entry.place) == target:
                return entry
            if isinstance(entry, Entry) and entry.swimmer and entry.swimmer.name.lower() == target:
                return entry
            if isinstance(entry, RelayEntry) and entry.team_name.lower() == target:
                return entry
        return None

    def scratch_entry(self, event_id: str, entry_id: str) -> ParseResult:
        """Scratch an athlete or relay from an event."""
        event = self._find_event(event_id)
        if not event:
            raise ValueError(f"Event not found: {event_id}")
        entry = self._find_entry(event, entry_id)
        if not entry:
            raise ValueError(f"Entry not found: {entry_id} in event {event_id}")

        if entry.status != "scratched":
            entry.status = "scratched"
            self.parse_result.edit_summary["scratches"] = (
                self.parse_result.edit_summary.get("scratches", 0) + 1
            )
        return self.parse_result

    def edit_entry_time(self, event_id: str, entry_id: str, new_time: str) -> ParseResult:
        """Update seed time for an existing entry."""
        event = self._find_event(event_id)
        if not event:
            raise ValueError(f"Event not found: {event_id}")
        entry = self._find_entry(event, entry_id)
        if not entry:
            raise ValueError(f"Entry not found: {entry_id} in event {event_id}")

        normalized_time = normalize_seed_time(new_time)
        entry.seed_time = normalized_time
        entry.edit_source = "user_edited"
        self.parse_result.edit_summary["time_edits"] = (
            self.parse_result.edit_summary.get("time_edits", 0) + 1
        )
        return self.parse_result

    def inject_entry(self, event_id: str, new_entry: Union[Entry, RelayEntry]) -> ParseResult:
        """Inject a new swimmer or relay entry into an event."""
        event = self._find_event(event_id)
        if not event:
            raise ValueError(f"Event not found: {event_id}")

        new_entry.edit_source = "user_injected"
        event.entries.append(new_entry)
        self.parse_result.edit_summary["injections"] = (
            self.parse_result.edit_summary.get("injections", 0) + 1
        )
        return self.parse_result

    def reseed_event(self, event_id: str, lanes: int = 8) -> HeatSheet:
        """Reseed an event using active (non-scratched) entries only."""
        event = self._find_event(event_id)
        if not event:
            raise ValueError(f"Event not found: {event_id}")

        active_entries = [e for e in event.entries if e.status != "scratched"]
        active_event = event.model_copy(update={"entries": active_entries})
        return seed_event(active_event, lanes=lanes)

    def get_edit_summary(self) -> str:
        """Return human-readable summary string of applied mutations."""
        s = self.parse_result.edit_summary
        return (
            f"Scratches: {s.get('scratches', 0)}, "
            f"Time Edits: {s.get('time_edits', 0)}, "
            f"Injections: {s.get('injections', 0)}"
        )
