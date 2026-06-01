from pydantic import BaseModel
from typing import List, Optional

class Swimmer(BaseModel):
    name: str
    age: Optional[int] = None
    team_code: str

class Entry(BaseModel):
    place: int
    swimmer: Swimmer
    seed_time: str
    
class RelayEntry(BaseModel):
    place: int
    team_name: str
    seed_time: str
    swimmers: Optional[List[str]] = None

class Event(BaseModel):
    number: int
    name: str
    gender: str
    distance: int
    stroke: str
    entries: List[Entry | RelayEntry] = []


class LaneAssignment(BaseModel):
    """A swimmer/relay assigned to a specific heat and lane."""
    entry: Entry | RelayEntry
    heat: int
    lane: int


class HeatSheet(BaseModel):
    """A complete heat sheet for an event with all lane assignments."""
    event: Event
    lanes: int  # Number of lanes (typically 8)
    heats: int  # Total number of heats
    assignments: List[LaneAssignment]  # All lane assignments sorted by heat/lane
