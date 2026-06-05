"""
HeatWave Streamlit UI - Psych Sheet to Heat Sheet Converter
Provides drag-and-drop PDF upload, live preview, and PDF generation.
Zero-persistent-storage design: All PDFs generated in temporary folders and auto-deleted.
"""
import io
import tempfile
from pathlib import Path
import streamlit as st
from datetime import datetime

from src.parser.extractor import extract_text_from_pdf, parse_events_from_text
from src.seeding.seeder import seed_event, format_heat_sheet
from src.core.pdf_generator import generate_full_meet_pdf, generate_heat_sheet_pdf
from src.core.timeline import (
    estimate_meet_timeline,
    lookup_swimmer_schedule,
    get_unique_swimmers,
    _format_duration,
)
from src.utils.cleanup import start_cleanup_daemon, clear_directory, cleanup_old_files


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="heatWave - Heat Sheet Generator",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3em;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 10px;
    }
    .subtitle {
        font-size: 1.2em;
        color: #666;
        margin-bottom: 30px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .duration-card {
        background: linear-gradient(135deg, #1f77b4, #0d4f8a);
        color: white;
        padding: 20px 24px;
        border-radius: 10px;
        text-align: center;
        margin: 8px 0;
    }
    .duration-label {
        font-size: 0.85em;
        opacity: 0.85;
        margin-bottom: 4px;
    }
    .duration-value {
        font-size: 2em;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .swimmer-row {
        padding: 10px 14px;
        border-radius: 6px;
        border: 1px solid #e0e0e0;
        margin-bottom: 6px;
        background: #fafafa;
        cursor: pointer;
    }
    .schedule-table th {
        background: #333;
        color: white;
        padding: 8px 12px;
    }
    .schedule-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #eee;
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def initialize_session_state():
    """Initialize session state variables."""
    defaults = {
        "pdf_uploaded": False,
        "events": None,
        "heat_sheets": None,
        "pdf_content": None,
        "timeline": None,
        "meet_title": "Swimming Meet",
        "meet_date": datetime.now().strftime("%m/%d/%Y"),
        "num_lanes": 8,
        "heat_gap_minutes": 2.0,
        "meet_start_time": "8:00 AM",
        "start_heat_number": 1,
        "swimmer_search_query": "",
        "selected_swimmer": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    if "cleanup_daemon" not in st.session_state:
        st.session_state.cleanup_daemon = start_cleanup_daemon(
            "data/output",
            check_interval_minutes=5,
            max_age_hours=1,
        )


def process_pdf(pdf_file):
    """Process uploaded PDF and extract events."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_file.getbuffer())
            tmp_path = tmp_file.name

        with st.spinner("Extracting text from PDF..."):
            text = extract_text_from_pdf(tmp_path)

        with st.spinner("Parsing events and entries..."):
            events = parse_events_from_text(text)

        Path(tmp_path).unlink()
        return events, text

    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return None, None


def seed_all_events(events, num_lanes):
    """Seed all events and return heat sheets."""
    try:
        heat_sheets = []
        progress_bar = st.progress(0)

        for idx, event in enumerate(events):
            if event.entries:
                heat_sheet = seed_event(event, lanes=num_lanes)
                heat_sheets.append(heat_sheet)
            progress_bar.progress((idx + 1) / len(events))

        return heat_sheets

    except Exception as e:
        st.error(f"Error seeding events: {str(e)}")
        return None


def generate_pdfs(heat_sheets, meet_title, meet_date, num_lanes, timeline=None):
    """Generate PDF files, optionally annotated with timeline data."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            with st.spinner("Generating complete meet PDF..."):
                full_pdf_path = tmpdir / "Full_Meet_Heatsheets.pdf"
                generate_full_meet_pdf(
                    heat_sheets,
                    str(full_pdf_path),
                    meet_title=meet_title,
                    meet_date=meet_date,
                    timeline=timeline,
                )
                with open(full_pdf_path, "rb") as f:
                    full_pdf_content = f.read()

            individual_pdfs = {}
            with st.spinner("Generating individual event PDFs..."):
                for heat_sheet in heat_sheets:
                    event = heat_sheet.event
                    pdf_path = tmpdir / f"Event_{event.number:02d}_Heatsheet.pdf"
                    generate_heat_sheet_pdf(
                        heat_sheet,
                        str(pdf_path),
                        meet_title=meet_title,
                        meet_date=meet_date,
                        timeline=timeline,
                    )
                    with open(pdf_path, "rb") as f:
                        individual_pdfs[event.number] = f.read()

            return full_pdf_content, individual_pdfs

    except Exception as e:
        st.error(f"Error generating PDFs: {str(e)}")
        return None, None


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    initialize_session_state()

    # Header
    st.markdown('<div class="main-header"> heatWave</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Psych Sheet to Heat Sheet Converter</div>',
        unsafe_allow_html=True,
    )

    has_heat_sheets = st.session_state.heat_sheets is not None

    # Build tab list — Find Swimmer only enabled after generation
    tab_labels = ["Upload", "Preview", "Settings", "Generate", "Find Swimmer"]
    tab1, tab2, tab3, tab4, tab5 = st.tabs(tab_labels)

    # ========================================================================
    # TAB 1: UPLOAD
    # ========================================================================
    with tab1:
        st.header("Upload Psych Sheet")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### Step 1: Choose Your PDF")
            uploaded_file = st.file_uploader(
                "Drag and drop your USA Swimming psych sheet PDF here",
                type="pdf",
                label_visibility="collapsed",
            )

            if uploaded_file is not None:
                st.session_state.pdf_uploaded = True
                st.markdown(
                    '<div class="success-box">PDF uploaded successfully!</div>',
                    unsafe_allow_html=True,
                )
                st.info(f"File: **{uploaded_file.name}**")
                st.info(f"Size: **{uploaded_file.size / 1024:.1f} KB**")

                if st.button("Parse PDF", type="primary", use_container_width=True):
                    events, text = process_pdf(uploaded_file)

                    if events:
                        st.session_state.events = events
                        st.session_state.pdf_uploaded = True
                        # Reset downstream state when a new file is loaded
                        st.session_state.heat_sheets = None
                        st.session_state.timeline = None
                        st.session_state.selected_swimmer = None

                        st.markdown(
                            '<div class="success-box">PDF parsed successfully!</div>',
                            unsafe_allow_html=True,
                        )

                        relay_count = sum(
                            1 for e in events
                            if e.entries and not hasattr(e.entries[0], "swimmer")
                        )
                        individual_count = sum(
                            1 for e in events
                            if e.entries and hasattr(e.entries[0], "swimmer")
                        )
                        total_entries = sum(len(e.entries) for e in events)

                        col_a, col_b, col_c, col_d = st.columns(4)
                        with col_a:
                            st.metric("Total Events", len(events))
                        with col_b:
                            st.metric("Relay Events", relay_count)
                        with col_c:
                            st.metric("Individual Events", individual_count)
                        with col_d:
                            st.metric("Total Entries", total_entries)

                        st.success("Ready to seed heats! Go to the **Settings** tab to customize.")

        with col2:
            st.markdown("### Info")
            st.markdown("""
            **Supported Format:**
            - USA Swimming psych sheets
            - Two-column layouts
            - Standard PDF format

            **What happens:**
            1. Extract swimmer data
            2. Parse events & entries
            3. Apply seeding rules
            4. Generate heat sheets
            """)

    # ========================================================================
    # TAB 2: PREVIEW
    # ========================================================================
    with tab2:
        st.header("Event Preview")

        if st.session_state.events is None:
            st.info("Upload and parse a PDF first to see the preview.")
        else:
            events = st.session_state.events
            st.markdown(f"### {len(events)} Events Found")

            col1, col2 = st.columns(2)
            with col1:
                event_type_filter = st.selectbox(
                    "Filter by type:", ["All", "Individual", "Relay"]
                )
            with col2:
                search_query = st.text_input("Search event name:", "")

            filtered_events = events
            if event_type_filter != "All":
                filtered_events = [
                    e for e in filtered_events
                    if (
                        (event_type_filter == "Individual"
                         and e.entries and hasattr(e.entries[0], "swimmer"))
                        or (event_type_filter == "Relay"
                            and e.entries and not hasattr(e.entries[0], "swimmer"))
                    )
                ]
            if search_query:
                filtered_events = [
                    e for e in filtered_events
                    if search_query.lower() in e.name.lower()
                ]

            for event in filtered_events[:10]:
                with st.expander(
                    f"Event {event.number}: {event.gender} {event.distance}Y "
                    f"{event.stroke} ({len(event.entries)} entries)"
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Distance:** {event.distance} yards")
                    with col2:
                        st.markdown(f"**Stroke:** {event.stroke}")
                    with col3:
                        st.markdown(f"**Entries:** {len(event.entries)}")

                    st.markdown("**Sample Entries:**")
                    for entry in event.entries[:5]:
                        if hasattr(entry, "swimmer"):
                            st.markdown(
                                f"- {entry.swimmer.name} ({entry.swimmer.age}yo, "
                                f"{entry.swimmer.team_code}) - {entry.seed_time}"
                            )
                        else:
                            st.markdown(f"- {entry.team_name} - {entry.seed_time}")

                    if len(event.entries) > 5:
                        st.caption(f"... and {len(event.entries) - 5} more entries")

            if len(filtered_events) > 10:
                st.caption(
                    f"Showing first 10 of {len(filtered_events)} events. "
                    "Use filters to narrow down."
                )

    # ========================================================================
    # TAB 3: SETTINGS
    # ========================================================================
    with tab3:
        st.header("Heat Sheet Settings")

        if st.session_state.events is None:
            st.info("Upload and parse a PDF first to configure settings.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Meet Information")
                meet_title = st.text_input(
                    "Meet Title:",
                    value=st.session_state.meet_title,
                    help="Display name for the meet",
                )
                meet_date = st.text_input(
                    "Meet Date:",
                    value=st.session_state.meet_date,
                    help="Date to display on heat sheets (format: MM/DD/YYYY)",
                )

            with col2:
                st.markdown("### Pool Configuration")
                num_lanes = st.number_input(
                    "Number of Lanes:",
                    min_value=4,
                    max_value=10,
                    value=int(st.session_state.num_lanes),
                    step=1,
                    help="Typical: 8 lanes",
                )
                st.markdown("*Seeding follows USA Swimming rules*")

            st.markdown("---")
            st.markdown("### Timeline Estimator")

            col3, col4, col5 = st.columns(3)

            with col3:
                meet_start_time = st.text_input(
                    "Session Start Time:",
                    value=st.session_state.meet_start_time,
                    help="Wall-clock time the session begins, e.g. 8:00 AM",
                )

            with col4:
                start_heat_number = st.number_input(
                    "Session Begins at Heat #:",
                    min_value=1,
                    max_value=50,
                    value=int(st.session_state.start_heat_number),
                    step=1,
                    help=(
                        "Heat number in the first event where the session clock "
                        "starts. Use 1 for a full-session estimate."
                    ),
                )

            with col5:
                heat_gap_minutes = st.number_input(
                    "Gap Between Heats (minutes):",
                    min_value=0.5,
                    max_value=10.0,
                    value=float(st.session_state.heat_gap_minutes),
                    step=0.5,
                    format="%.1f",
                    help=(
                        "Time added between heats to account for check-in, "
                        "clearing the deck, and the start signal."
                    ),
                )

            st.caption(
                "NT (no-time) heats default to 2 min for events 400Y and under, "
                "or 5 min for longer events."
            )

            # Persist settings
            st.session_state.meet_title = meet_title
            st.session_state.meet_date = meet_date
            st.session_state.num_lanes = num_lanes
            st.session_state.meet_start_time = meet_start_time
            st.session_state.start_heat_number = start_heat_number
            st.session_state.heat_gap_minutes = heat_gap_minutes

            # Preview row
            st.markdown("---")
            st.markdown("### Current Settings")
            col_a, col_b, col_c, col_d, col_e = st.columns(5)
            with col_a:
                st.markdown(f"**Meet:** {meet_title}")
            with col_b:
                st.markdown(f"**Date:** {meet_date}")
            with col_c:
                st.markdown(f"**Lanes:** {num_lanes}")
            with col_d:
                st.markdown(f"**Start:** {meet_start_time}")
            with col_e:
                st.markdown(f"**Gap:** {heat_gap_minutes} min")

    # ========================================================================
    # TAB 4: GENERATE
    # ========================================================================
    with tab4:
        st.header("Generate Heat Sheets")

        if st.session_state.events is None:
            st.warning("Please upload and parse a PDF first.")
        else:
            meet_title = st.session_state.get("meet_title", "Swimming Meet")
            meet_date = st.session_state.get("meet_date", datetime.now().strftime("%m/%d/%Y"))
            num_lanes = st.session_state.get("num_lanes", 8)
            heat_gap = float(st.session_state.get("heat_gap_minutes", 2.0))
            meet_start = st.session_state.get("meet_start_time", "8:00 AM")
            start_heat = int(st.session_state.get("start_heat_number", 1))

            events = st.session_state.events

            st.markdown(f"""
            ### Ready to Generate Heat Sheets

            **Configuration:**
            - Meet: {meet_title}
            - Date: {meet_date}
            - Lanes: {num_lanes}
            - Events: {len(events)}
            - Total Entries: {sum(len(e.entries) for e in events)}
            - Session Start: {meet_start} (Heat {start_heat})
            - Heat Gap: {heat_gap} min
            """)

            if st.button(
                "Generate Heat Sheets", type="primary",
                use_container_width=True, key="generate_btn"
            ):
                heat_sheets = seed_all_events(events, num_lanes)

                if heat_sheets:
                    st.session_state.heat_sheets = heat_sheets

                    # Compute timeline immediately after seeding
                    timeline = estimate_meet_timeline(
                        heat_sheets,
                        gap_minutes=heat_gap,
                        meet_start_time=meet_start,
                        start_heat_number=start_heat,
                    )
                    st.session_state.timeline = timeline

                    # Reset swimmer selection when re-generating
                    st.session_state.selected_swimmer = None

                    st.markdown(
                        '<div class="success-box">Events seeded successfully!</div>',
                        unsafe_allow_html=True,
                    )

                    # Metrics row
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Total Heats", sum(h.heats for h in heat_sheets))
                    with col2:
                        total_assigned = sum(len(h.assignments) for h in heat_sheets)
                        total_heats = sum(h.heats for h in heat_sheets)
                        avg = total_assigned / total_heats if total_heats else 0
                        st.metric("Avg Entries/Heat", f"{avg:.1f}")
                    with col3:
                        largest = max(heat_sheets, key=lambda h: len(h.assignments))
                        st.metric("Largest Event", f"{len(largest.assignments)} entries")
                    with col4:
                        smallest = min(heat_sheets, key=lambda h: len(h.assignments))
                        st.metric("Smallest Event", f"{len(smallest.assignments)} entries")
                    with col5:
                        st.markdown(
                            f'<div class="duration-card">'
                            f'<div class="duration-label">Est. Meet Duration</div>'
                            f'<div class="duration-value">{timeline.format_total()}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    with st.expander("View Heat Details"):
                        for heat_sheet in heat_sheets[:5]:
                            event = heat_sheet.event
                            st.markdown(
                                f"**Event {event.number}: {event.gender} "
                                f"{event.distance}Y {event.stroke}**"
                            )
                            heats_by_num = {}
                            for assignment in heat_sheet.assignments:
                                heats_by_num.setdefault(assignment.heat, []).append(assignment)

                            heat_sizes = [
                                len(heats_by_num.get(h, []))
                                for h in range(1, heat_sheet.heats + 1)
                            ]
                            st.markdown(
                                f"- Heats: {heat_sheet.heats} | Distribution: {heat_sizes}"
                            )

                        if len(heat_sheets) > 5:
                            st.caption(f"... and {len(heat_sheets) - 5} more events")

            # Download section (persists across reruns)
            if st.session_state.heat_sheets:
                st.markdown("---")
                st.markdown("### Download Heat Sheets")

                timeline = st.session_state.get("timeline")

                full_pdf, individual_pdfs = generate_pdfs(
                    st.session_state.heat_sheets,
                    meet_title,
                    meet_date,
                    num_lanes,
                    timeline=timeline,
                )

                if full_pdf:
                    col1, col2 = st.columns(2)

                    with col1:
                        st.download_button(
                            label="Download Full Meet PDF",
                            data=full_pdf,
                            file_name=f"HeatSheet_{meet_title.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )

                    with col2:
                        page_count = len(st.session_state.heat_sheets) + 1
                        st.info(
                            f"File size: {len(full_pdf) / 1024:.1f} KB | "
                            f"{page_count} pages"
                        )

                    if individual_pdfs:
                        st.markdown("**Individual Event Heat Sheets:**")
                        cols = st.columns(min(4, len(individual_pdfs)))
                        for idx, (event_num, pdf_content) in enumerate(
                            sorted(individual_pdfs.items())
                        ):
                            with cols[idx % len(cols)]:
                                st.download_button(
                                    label=f"Event {event_num}",
                                    data=pdf_content,
                                    file_name=f"Event_{event_num:02d}_Heatsheet.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"download_event_{event_num}",
                                )

    # ========================================================================
    # TAB 5: FIND SWIMMER
    # ========================================================================
    with tab5:
        st.header("Find Swimmer")

        if not has_heat_sheets or st.session_state.heat_sheets is None:
            st.info(
                "Generate heat sheets first (Generate tab) to use the swimmer lookup."
            )
        else:
            heat_sheets = st.session_state.heat_sheets
            timeline = st.session_state.get("timeline")

            st.markdown(
                "Search for any swimmer by part of their first or last name. "
                "Relay entries are not included."
            )

            # ---- Search bar ----
            query = st.text_input(
                "Swimmer name (partial match):",
                value=st.session_state.swimmer_search_query,
                placeholder="e.g. Smith or Emma",
                key="swimmer_search_input",
            )
            st.session_state.swimmer_search_query = query

            if query.strip():
                results = lookup_swimmer_schedule(query, heat_sheets, timeline)

                if not results:
                    st.warning(f"No individual swimmers found matching \"{query}\".")
                else:
                    # Deduplicate unique swimmers from results
                    seen: dict[str, dict] = {}
                    for r in results:
                        key = f"{r['swimmer_name']}|{r['team_code']}"
                        if key not in seen:
                            seen[key] = {
                                "swimmer_name": r["swimmer_name"],
                                "team_code": r["team_code"],
                                "event_count": 0,
                            }
                        seen[key]["event_count"] += 1

                    unique_swimmers = list(seen.values())
                    unique_swimmers.sort(key=lambda s: s["swimmer_name"].lower())

                    st.markdown(
                        f"**{len(unique_swimmers)} swimmer(s) found** matching "
                        f"\"{query}\":"
                    )

                    # ---- Swimmer list ----
                    for swimmer in unique_swimmers:
                        label = (
                            f"{swimmer['swimmer_name']}  |  "
                            f"{swimmer['team_code']}  |  "
                            f"{swimmer['event_count']} event(s)"
                        )
                        if st.button(label, key=f"sel_{swimmer['swimmer_name']}_{swimmer['team_code']}"):
                            st.session_state.selected_swimmer = swimmer

                    # ---- Detail view ----
                    selected = st.session_state.get("selected_swimmer")
                    if selected:
                        st.markdown("---")
                        st.markdown(
                            f"### Schedule: {selected['swimmer_name']}  "
                            f"*({selected['team_code']})*"
                        )

                        schedule = [
                            r for r in results
                            if r["swimmer_name"] == selected["swimmer_name"]
                            and r["team_code"] == selected["team_code"]
                        ]

                        # Build display table
                        headers = ["Event", "Heat", "Lane", "Seed Time", "Est. Start"]
                        rows = []
                        for r in schedule:
                            rows.append([
                                r["event_name"],
                                r["heat"],
                                r["lane"],
                                r["seed_time"],
                                r["est_start"] if r["est_start"] else "—",
                            ])

                        import pandas as pd
                        df = pd.DataFrame(rows, columns=headers)
                        st.dataframe(df, use_container_width=True, hide_index=True)

                        st.caption(
                            f"{len(schedule)} individual event(s) for "
                            f"{selected['swimmer_name']}."
                        )

            else:
                st.caption(
                    "Start typing a name above to search. "
                    f"Heat sheets contain {len(heat_sheets)} seeded events."
                )

    # ========================================================================
    # FOOTER
    # ========================================================================
    st.markdown("---")
    st.markdown("""
    <div class="info-box">
    <b>💡 Tips:</b>
    <br>1. Upload a USA Swimming psych sheet PDF
    <br>2. Check the preview to verify parsing
    <br>3. Customize settings (meet name, date, lanes, timeline gap)
    <br>4. Generate heat sheets — estimated meet duration is shown automatically
    <br>5. Use Find Swimmer to look up any athlete's heat, lane, and start time
    <br>6. Download as PDF for printing at meets
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
