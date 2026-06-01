import math
from typing import List, Tuple
from src.models.schemas import Event, Entry, RelayEntry, LaneAssignment, HeatSheet


def time_to_seconds(time_str: str) -> float:
    """
    Convert seed time string to seconds for sorting.
    
    Args:
        time_str: Time in MM:SS.XX or NT format
    
    Returns:
        Float seconds, or infinity for NT (no time)
    """
    if time_str.upper() == "NT":
        return float('inf')
    
    try:
        parts = time_str.split(":")
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    except (IndexError, ValueError):
        return float('inf')


def get_center_out_lanes(num_lanes: int) -> List[int]:
    """
    Generate the center-out lane placement pattern for USA Swimming seeding.
    
    For 8 lanes: [4, 5, 3, 6, 2, 7, 1, 8]
    For 6 lanes: [3, 4, 2, 5, 1, 6]
    
    The first swimmer (fastest in heat) gets the center lane,
    then alternates outward to each side.
    
    Args:
        num_lanes: Number of lanes in the pool
    
    Returns:
        List of lanes in placement order
    """
    if num_lanes == 0:
        return []
    
    lanes = []
    left = (num_lanes // 2)      # Center-left lane (1-indexed)
    right = left + 1             # Center-right lane (1-indexed)
    
    # Alternate placement: left first, then right, expanding outward
    max_iterations = num_lanes
    for _ in range(max_iterations):
        if left >= 1 and len(lanes) < num_lanes:
            lanes.append(left)
            left -= 1
        if right <= num_lanes and len(lanes) < num_lanes:
            lanes.append(right)
            right += 1
    
    return lanes[:num_lanes]


def sort_entries_by_time(entries: List[Entry | RelayEntry]) -> List[Entry | RelayEntry]:
    """
    Sort entries by seed time (fastest last, slowest first).
    This is the order for filling heats from slowest to fastest.
    
    Args:
        entries: List of entries to sort
    
    Returns:
        Sorted entries (slowest first, fastest last)
    """
    def get_time_seconds(entry):
        return time_to_seconds(entry.seed_time)
    
    # Sort ascending (slowest first, fastest last)
    return sorted(entries, key=get_time_seconds, reverse=True)


def seed_event(event: Event, lanes: int = 8) -> HeatSheet:
    """
    Apply USA Swimming prelim seeding rules to an event's entries.
    
    Rules:
    1. Sort entries by seed time (slowest to fastest)
    2. Fill heats from slowest to fastest swimmers
    3. Within each heat, place swimmers center-out (fastest in center lanes)
    4. If heats aren't full, first heat gets empty lanes (not last heat)
    
    Args:
        event: Event with parsed entries
        lanes: Number of lanes available (default 8)
    
    Returns:
        HeatSheet with heat and lane assignments
    """
    if not event.entries:
        return HeatSheet(event=event, lanes=lanes, heats=0, assignments=[])
    
    # Sort entries by seed time (slowest first, fastest last)
    sorted_entries = sort_entries_by_time(event.entries)
    
    # Calculate number of heats needed
    num_heats = math.ceil(len(sorted_entries) / lanes)
    
    # Get center-out lane placement pattern
    lane_pattern = get_center_out_lanes(lanes)
    
    assignments: List[LaneAssignment] = []
    
    # Calculate remainder to determine first heat size
    remainder = len(sorted_entries) % lanes
    if remainder == 0:
        remainder = lanes  # If evenly divisible, first heat is full
    
    # Fill heats from slowest to fastest
    # If incomplete, first heat gets partial swimmers (with empty lanes)
    for heat_num in range(1, num_heats + 1):
        if remainder > 0 and heat_num == 1:
            # First heat: partial (with empty lanes)
            start_idx = 0
            end_idx = remainder
        else:
            # Other heats: full
            if remainder > 0 and len(sorted_entries) % lanes != 0:
                # Account for the reduced first heat in calculations
                start_idx = remainder + (heat_num - 2) * lanes
            else:
                start_idx = (heat_num - 1) * lanes
            end_idx = start_idx + lanes
        
        heat_entries = sorted_entries[start_idx:end_idx]
        
        # Reverse to put fastest first in heat for center-out placement
        heat_entries.reverse()
        
        # Assign lanes using center-out pattern
        for position, entry in enumerate(heat_entries):
            lane = lane_pattern[position]
            assignments.append(LaneAssignment(entry=entry, heat=heat_num, lane=lane))
    
    # Sort assignments by heat then lane for output
    assignments.sort(key=lambda a: (a.heat, a.lane))
    
    return HeatSheet(
        event=event,
        lanes=lanes,
        heats=num_heats,
        assignments=assignments
    )


def format_heat_sheet(heat_sheet: HeatSheet) -> str:
    """
    Format a heat sheet for display/printing.
    
    Args:
        heat_sheet: HeatSheet to format
    
    Returns:
        Formatted string representation
    """
    lines = []
    lines.append(f"Event {heat_sheet.event.number}: {heat_sheet.event.gender} {heat_sheet.event.distance}Y {heat_sheet.event.stroke}")
    lines.append(f"Total Heats: {heat_sheet.heats} | Total Entries: {len(heat_sheet.assignments)}")
    lines.append("")
    
    current_heat = None
    
    for assignment in heat_sheet.assignments:
        if assignment.heat != current_heat:
            if current_heat is not None:
                lines.append("")
            current_heat = assignment.heat
            lines.append(f"Heat {assignment.heat}:")
            lines.append("-" * 80)
        
        entry = assignment.entry
        if isinstance(entry, Entry):
            swimmer = entry.swimmer
            lines.append(f"  Lane {assignment.lane}: {swimmer.name} (Age {swimmer.age}) {swimmer.team_code} - {entry.seed_time}")
        else:
            lines.append(f"  Lane {assignment.lane}: {entry.team_name} - {entry.seed_time}")
    
    return "\n".join(lines)
