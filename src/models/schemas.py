from pydantic import BaseModel, Field
from typing import List, Optional, Union

class Swimmer(BaseModel):
    name: str
    age: Optional[int] = None
    year: Optional[str] = None       # FR, SO, JR, SR, GR, GS
    team_code: str

class Entry(BaseModel):
    place: int
    swimmer: Swimmer
    seed_time: str
    low_confidence: bool = False
    error_msg: str = ""
    
class RelayEntry(BaseModel):
    place: int
    team_name: str
    seed_time: str
    swimmers: Optional[List[str]] = None
    low_confidence: bool = False
    error_msg: str = ""


class Event(BaseModel):
    number: int
    event_label: Optional[str] = None   # raw label for non-numeric event IDs like "41X"
    name: str
    gender: str
    distance: int
    stroke: str
    entries: List[Entry | RelayEntry] = []
    layout_confidence_low: bool = False   # Sparse page detected; previous boundary map used
    auto_layout_failed: bool = False      # Histogram produced 0 or >3 columns with no fallback
    is_exhibition: bool = False         # True for "X"-suffixed exhibition events


class LaneAssignment(BaseModel):
    """A swimmer/relay assigned to a specific heat and lane."""
    entry: Union[Entry, RelayEntry]
    heat: int
    lane: int
    est_start_time: Optional[str] = None  # wall-clock string, e.g. "9:14 AM"


class HeatSheet(BaseModel):
    """A complete heat sheet for an event with all lane assignments."""
    event: Event
    lanes: int  # Number of lanes (typically 8)
    heats: int  # Total number of heats
    assignments: List[LaneAssignment]  # All lane assignments sorted by heat/lane


class SessionConfig(BaseModel):
    """Configuration for a multi-session meet schedule."""
    start_event_num: int = Field(..., description="First event number assigned to this session")
    start_time: str = Field(default="8:00 AM", description="Wall-clock start time, e.g. '8:00 AM'")
    session_name: str = Field(default="", description="Display name for this session, e.g. 'Morning Session'")


class ValidationResult(BaseModel):
    """Result payload from the psych sheet event validation engine."""
    is_valid: bool = True
    warnings: List[str] = []
    errors: List[str] = []
    confidence_score: float = 1.0

