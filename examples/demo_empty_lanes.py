"""
Demo: Empty lanes now in first heat instead of last heat
This script shows the difference in heat assignment with the updated seeding logic.
"""
from src.seeding.seeder import seed_event
from src.models.schemas import Event, Entry, Swimmer


def demo_empty_lanes_in_first_heat():
    """Show how empty lanes are now assigned to the first heat."""
    
    # Create 10 swimmers (with 8-lane pool = 2 heats, second one partial)
    swimmers = [Swimmer(name=f"Swimmer {i:02d}", age=10, team_code=f"TEAM{i}") for i in range(1, 11)]
    
    entries = [
        Entry(
            place=i,
            swimmer=swimmers[i-1],
            seed_time=f"2:{59-i*2:02d}.00"  # Slowest to fastest
        )
        for i in range(1, 11)
    ]
    
    event = Event(
        number=1,
        name="Demo Event",
        gender="Boys",
        distance=200,
        stroke="Freestyle",
        entries=entries
    )
    
    # Seed the event
    heat_sheet = seed_event(event, lanes=8)
    
    print("="*70)
    print("DEMO: EMPTY LANES IN FIRST HEAT")
    print("="*70)
    print(f"\nTotal swimmers: {len(entries)}")
    print(f"Pool lanes: 8")
    print(f"Heats needed: {heat_sheet.heats}")
    print()
    
    # Display heats
    for heat_num in range(1, heat_sheet.heats + 1):
        assignments = [a for a in heat_sheet.assignments if a.heat == heat_num]
        filled_lanes = len(assignments)
        empty_lanes = 8 - filled_lanes
        
        print(f"Heat {heat_num}: {filled_lanes} swimmers, {empty_lanes} empty lanes")
        for assignment in assignments:
            entry = assignment.entry
            print(f"  Lane {assignment.lane}: {entry.swimmer.name} ({entry.seed_time})")
        
        if empty_lanes > 0:
            print(f"  Lanes {', '.join(str(i) for i in range(1, 9) if i not in [a.lane for a in assignments])}: EMPTY")
        print()
    
    print("="*70)
    print("✓ Notice: Heat 1 has 2 swimmers and 6 empty lanes")
    print("✓ Heat 2 has 8 swimmers (full)")
    print("="*70)


if __name__ == "__main__":
    demo_empty_lanes_in_first_heat()
