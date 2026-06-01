import re
from typing import List, Tuple
import pdfplumber
from ..models.schemas import Event, Entry, RelayEntry, Swimmer


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a Psych Sheet PDF.
    Handles the two-column layout parsing by extracting left and right columns separately.
    
    Returns:
        Full text with columns merged in reading order.
    """
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page_num, page in enumerate(pdf.pages):
            width = page.width
            height = page.height
            
            # Crop left and right columns
            left_bbox = (0, 0, width / 2, height)
            right_bbox = (width / 2, 0, width, height)
            
            left_col = page.crop(left_bbox)
            right_col = page.crop(right_bbox)
            
            left_text = left_col.extract_text() or ""
            right_text = right_col.extract_text() or ""
            
            # Merge columns intelligently (left then right)
            if page_num > 0:
                full_text += "\n"
            full_text += left_text + "\n" + right_text
        
        return full_text


def parse_event_header(line: str) -> Tuple[int, str, str, int, str] | None:
    """
    Parse event header line: "Event 1 Girls 10 & Under 200 Yard Freestyle"
    
    Returns:
        Tuple of (event_number, gender, event_name, distance, stroke) or None if not matched.
    """
    # Pattern: Event N Gender AgeGroup DistanceYards StrokeStroke...
    pattern = r"Event\s+(\d+)\s+(Girls|Boys|Women|Men)\s+(.+?)\s+(\d+)\s+Yard\s+(.+?)(?:\s+Relay)?$"
    
    match = re.match(pattern, line.strip())
    if match:
        event_num = int(match.group(1))
        gender = match.group(2)
        age_group = match.group(3)  # e.g., "10 & Under"
        distance = int(match.group(4))
        stroke = match.group(5)
        
        # Construct full event name
        event_name = f"{age_group} {distance}Y {stroke}"
        
        return (event_num, gender, event_name, distance, stroke)
    
    return None


def parse_seed_time(time_str: str) -> str:
    """
    Parse and validate seed time formats (MM:SS.XX or NT).
    
    Returns:
        Normalized seed time string.
    """
    time_str = time_str.strip().upper()
    
    # Handle NT (no time)
    if time_str == "NT":
        return "NT"
    
    # Handle MM:SS.XX format
    if re.match(r"^\d+:\d{2}\.\d{2}$", time_str):
        return time_str
    
    # Handle partial formats
    if re.match(r"^\d+:\d{2}$", time_str):
        return time_str + ".00"
    
    return time_str


def parse_individual_entry(line: str) -> Tuple[int, str, int, str, str] | None:
    """
    Parse individual swimmer entry: "1 Meek, Keaston 10 Bartlesville Spl-OK 2:42.05"
    
    Returns:
        Tuple of (place, swimmer_name, age, team_code, seed_time) or None if not matched.
    """
    # Pattern: place name age team seed_time
    parts = line.split()
    
    if len(parts) < 5:
        return None
    
    try:
        place = int(parts[0])
    except ValueError:
        return None
    
    # Work backwards: seed_time is last, age is a number that comes before team
    # Find seed_time (last part, should match time pattern)
    seed_time_str = parts[-1]
    if not (re.match(r"^\d+:\d{2}", seed_time_str) or seed_time_str.upper() == "NT"):
        return None
    
    seed_time = parse_seed_time(seed_time_str)
    
    # Find age: scan from end backwards (before seed_time) looking for age pattern
    # Age is typically 1-2 digits, and comes after name, before team
    age = None
    age_idx = -1
    
    for i in range(len(parts) - 2, 0, -1):  # Start before seed_time
        if re.match(r"^\d{1,2}$", parts[i]):  # 1-2 digit number
            try:
                age = int(parts[i])
                age_idx = i
                break
            except ValueError:
                continue
    
    if age_idx < 2:  # Need at least place and name before age
        return None
    
    # Name is everything between place and age
    name = " ".join(parts[1:age_idx])
    
    # Team code is everything between age and seed_time
    if age_idx + 1 >= len(parts) - 1:  # Make sure there's a team between age and seed_time
        return None
    
    team_code = " ".join(parts[age_idx + 1:-1])
    
    return (place, name, age, team_code, seed_time)


def parse_relay_entry(line: str) -> Tuple[int, str, str] | None:
    """
    Parse relay entry: "1 King Marlin Swim-OK A 2:13.43"
    
    Returns:
        Tuple of (place, team_name, seed_time) or None if not matched.
    """
    parts = line.split()
    
    if len(parts) < 3:
        return None
    
    try:
        place = int(parts[0])
    except ValueError:
        return None
    
    # Find seed time (last part, should be MM:SS.XX or NT)
    seed_time_str = parts[-1]
    if not (re.match(r"^\d+:\d{2}", seed_time_str) or seed_time_str.upper() == "NT"):
        return None
    
    # Team everything in between place and seed time
    team_name = " ".join(parts[1:-1])
    seed_time = parse_seed_time(seed_time_str)
    
    return (place, team_name, seed_time)


def parse_events_from_text(text: str) -> List[Event]:
    """
    Parse all events from extracted psych sheet text.
    
    Returns:
        List of Event objects with parsed entries.
    """
    lines = text.split("\n")
    events: List[Event] = []
    
    current_event: Event | None = None
    is_relay_event = False
    
    for line in lines:
        line = line.strip()
        
        if not line:
            continue
        
        # Check for event header
        event_info = parse_event_header(line)
        if event_info:
            # Save previous event if it exists
            if current_event:
                events.append(current_event)
            
            event_num, gender, event_name, distance, stroke = event_info
            is_relay_event = "Relay" in line
            
            current_event = Event(
                number=event_num,
                name=event_name,
                gender=gender,
                distance=distance,
                stroke=stroke,
                entries=[]
            )
            continue
        
        # Skip header lines
        if any(skip in line for skip in ["Name Age Team", "Team Relay Seed", "Seed Time", "HY-TEK"]):
            continue
        
        # Parse entries
        if current_event:
            if is_relay_event:
                entry_data = parse_relay_entry(line)
                if entry_data:
                    place, team_name, seed_time = entry_data
                    relay_entry = RelayEntry(
                        place=place,
                        team_name=team_name,
                        seed_time=seed_time
                    )
                    current_event.entries.append(relay_entry)
            else:
                entry_data = parse_individual_entry(line)
                if entry_data:
                    place, name, age, team_code, seed_time = entry_data
                    swimmer = Swimmer(name=name, age=age, team_code=team_code)
                    entry = Entry(place=place, swimmer=swimmer, seed_time=seed_time)
                    current_event.entries.append(entry)
    
    # Don't forget the last event
    if current_event:
        events.append(current_event)
    
    return events
