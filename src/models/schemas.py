from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal, Dict, Any

class Swimmer(BaseModel):
    name: str
    age: Optional[int] = None
    year: Optional[str] = None       # FR, SO, JR, SR, GR, GS
    team_code: str

class Entry(BaseModel):
    place: int
    swimmer: Swimmer
    seed_time: str
    status: Literal["active", "scratched", "exhibition"] = "active"
    edit_source: Literal["parsed", "user_edited", "user_injected"] = "parsed"
    low_confidence: bool = False
    error_msg: str = ""
    
class RelayEntry(BaseModel):
    place: int
    team_name: str
    seed_time: str
    swimmers: Optional[List[str]] = None
    status: Literal["active", "scratched", "exhibition"] = "active"
    edit_source: Literal["parsed", "user_edited", "user_injected"] = "parsed"
    low_confidence: bool = False
    error_msg: str = ""


class Event(BaseModel):
    number: int
    event_id: str = ""
    event_label: Optional[str] = None   # raw label for non-numeric event IDs like "41X"
    name: str
    gender: str
    distance: int
    stroke: str
    session: Literal["morning", "afternoon", "finals", "unassigned"] = "unassigned"
    entries: List[Union[Entry, RelayEntry]] = Field(default_factory=list)
    layout_confidence_low: bool = False   # Sparse page detected; previous boundary map used
    auto_layout_failed: bool = False      # Histogram produced 0 or >3 columns with no fallback
    is_exhibition: bool = False         # True for "X"-suffixed exhibition events

    def model_post_init(self, __context: Any) -> None:
        if not self.event_id:
            cleaned_stroke = self.stroke.lower().replace(" ", "_")
            cleaned_gender = self.gender.lower().replace(" ", "_")
            self.event_id = f"event_{self.number}_{cleaned_gender}_{self.distance}_{cleaned_stroke}"


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
    pdf_producer: Optional[str] = None


class ParseResult(BaseModel):
    """Encapsulates raw extraction, validation payload, metadata, and mutation summary."""
    events: List[Event] = Field(default_factory=list)
    validation: ValidationResult = Field(default_factory=ValidationResult)
    pdf_producer: Optional[str] = None
    edit_summary: Dict[str, int] = Field(default_factory=lambda: {"scratches": 0, "time_edits": 0, "injections": 0})

    def __iter__(self):
        return iter((self.events, self.validation))
