"""
HeatWave Streamlit UI - Psych Sheet to Heat Sheet Converter
Provides drag-and-drop PDF upload, live preview, and PDF generation.
Zero-persistent-storage design: All PDFs generated in temporary folders and auto-deleted.
"""
import io
import os
import re
import tempfile
from pathlib import Path
import streamlit as st
from datetime import datetime

from src.parser.extractor import (
    extract_text_from_pdf,
    parse_events_from_text,
    parse_pdf_via_spatial_engine,
)
from src.seeding.seeder import seed_event, format_heat_sheet
from src.core.pdf_generator import generate_full_meet_pdf, generate_heat_sheet_pdf
from src.core.timeline import (
    estimate_meet_timeline,
    lookup_swimmer_schedule,
    get_unique_swimmers,
    _format_duration,
)
from src.models.schemas import SessionConfig
from src.utils.cleanup import start_cleanup_daemon, clear_directory, cleanup_old_files


def sanitize_file_name(value: str) -> str:
    """Return a safe filename by replacing unsupported characters."""
    if not isinstance(value, str):
        return ""
    safe = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', value)
    safe = re.sub(r'\s+', '_', safe).strip('_')
    return safe[:100] or "HeatSheet"


def get_downloads_folder() -> Path:
    """Get the user's Downloads folder."""
    return Path.home() / "Downloads"


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

def get_app_writable_dir() -> Path:
    """
    Return a writable data directory that works in both portable and installed modes.
    Portable : resolves to <cwd>/data/output  (original behavior)
    Installed: resolves to %LOCALAPPDATA%/heatWave/output  (avoids Program Files ACL)
    """
    program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
    cwd = Path.cwd()

    # If running from inside Program Files, redirect to user-local AppData
    try:
        cwd.relative_to(program_files)
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "heatWave" / "output"
    except ValueError:
        # Not inside Program Files — use the original relative path
        base = cwd / "data" / "output"

    base.mkdir(parents=True, exist_ok=True)
    return base

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
        "sessions": [],              # list of session dicts for multi-session mode
        "multi_session_mode": False, # toggle state
        # Phase 6 — spatial layout flags
        "auto_layout_failed": False,  # True when histogram produced no usable boundaries
        "pdf_bytes_for_retry": None,  # Raw uploaded bytes kept in memory for column override retry
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    if "cleanup_daemon" not in st.session_state:
        st.session_state.cleanup_daemon = start_cleanup_daemon(
            str(get_app_writable_dir()),
            check_interval_minutes=5,
            max_age_hours=1,
        )



def process_pdf(pdf_file, column_override: int | None = None):
    """Process uploaded PDF through the spatial layout engine and extract events.

    Stores the raw uploaded bytes in session state so the user can re-process
    with a manual column override without re-uploading the file.

    Args:
        pdf_file: The Streamlit UploadedFile object.
        column_override: Optional 1/2/3 to force a specific column layout,
            bypassing histogram detection entirely.

    Returns:
        Tuple of (events, raw_bytes) where raw_bytes are the original PDF bytes.
    """
    try:
        raw_bytes = pdf_file.getbuffer().tobytes()
        # Store bytes in session state for potential retry with column_override
        st.session_state.pdf_bytes_for_retry = raw_bytes

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(raw_bytes)
            tmp_path = tmp_file.name

        with st.spinner("Analyzing layout and parsing events..."):
            events = parse_pdf_via_spatial_engine(tmp_path, column_override=column_override)

        Path(tmp_path).unlink(missing_ok=True)
        return events, raw_bytes

    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return None, None


def reprocess_pdf_with_override(column_override: int) -> list:
    """Re-run the spatial engine using bytes already stored in session state.

    Called by the manual column-override retry button.  Saves the in-memory
    bytes to a fresh temp file rather than keeping the original descriptor alive
    across Streamlit reruns.

    Args:
        column_override: 1, 2, or 3 — forces the corresponding column layout.

    Returns:
        List of Event objects, or empty list on failure.
    """
    raw_bytes = st.session_state.get("pdf_bytes_for_retry")
    if not raw_bytes:
        st.error("No PDF bytes available for retry. Please re-upload the file.")
        return []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(raw_bytes)
            tmp_path = tmp_file.name

        with st.spinner(f"Re-processing with {column_override}-column layout..."):
            events = parse_pdf_via_spatial_engine(tmp_path, column_override=column_override)

        Path(tmp_path).unlink(missing_ok=True)
        return events

    except Exception as e:
        st.error(f"Error re-processing PDF: {str(e)}")
        return []


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
                    lbl = event.event_label if event.event_label else f"{event.number:02d}"
                    pdf_path = tmpdir / f"Event_{lbl}_Heatsheet.pdf"
                    generate_heat_sheet_pdf(
                        heat_sheet,
                        str(pdf_path),
                        meet_title=meet_title,
                        meet_date=meet_date,
                        timeline=timeline,
                    )
                    with open(pdf_path, "rb") as f:
                        individual_pdfs[event.event_label or event.number] = f.read()

            return full_pdf_content, individual_pdfs

    except Exception as e:
        st.error(f"Error generating PDFs: {str(e)}")
        return None, None


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    initialize_session_state()
    events = st.session_state.events

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

        st.markdown("### Step 1: Choose Your PDF")
        uploaded_file = st.file_uploader(
            "Drag and drop your USA Swimming psych sheet PDF here",
            type="pdf",
            label_visibility="collapsed",
            accept_multiple_files=False,
        )

        if uploaded_file is not None:
            st.session_state.pdf_uploaded = True
            st.markdown(
                '<div class="success-box">PDF uploaded successfully!</div>',
                unsafe_allow_html=True,
            )
            st.info(f"File: **{uploaded_file.name}**")
            st.info(f"Size: **{uploaded_file.size / 1024:.1f} KB**")

            if st.button("Parse PDF", type="primary", width='stretch'):
                events, _raw = process_pdf(uploaded_file)

                if events:
                    st.session_state.events = events
                    st.session_state.pdf_uploaded = True
                    # Reset downstream state when a new file is loaded
                    st.session_state.heat_sheets = None
                    st.session_state.timeline = None
                    st.session_state.selected_swimmer = None

                    # Propagate layout flags into session state
                    auto_layout_failed = any(e.auto_layout_failed for e in events)
                    st.session_state.auto_layout_failed = auto_layout_failed

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

                    # --------------------------------------------------------
                    # Phase 6.4 — Manual column override safety net
                    # Rendered only when the histogram could not determine
                    # column structure automatically.
                    # --------------------------------------------------------
                    if st.session_state.get("auto_layout_failed", False):
                        st.error(
                            "⚠️ Layout analyzer could not determine column structure "
                            "automatically. Please select the column format manually below."
                        )
                        manual_columns = st.radio(
                            "Select column format manually:",
                            options=[1, 2, 3],
                            index=1,
                            key="manual_col_radio",
                            help=(
                                "1 = single column, "
                                "2 = standard two-column (most Hy-Tek sheets), "
                                "3 = three-column championship format"
                            ),
                        )
                        if st.button("Re-process Document", key="reprocess_btn", type="primary"):
                            retried_events = reprocess_pdf_with_override(manual_columns)
                            if retried_events:
                                st.session_state.events = retried_events
                                st.session_state.auto_layout_failed = False
                                st.session_state.heat_sheets = None
                                st.session_state.timeline = None
                                st.rerun()
                    else:
                        st.success("Ready to seed heats! Go to the **Settings** tab to customize.")

        # Reset state button
        if st.session_state.events is not None:
            st.markdown("---")
            if st.button("🔄 Reset State", type="secondary", width='stretch'):
                st.session_state.pdf_uploaded = False
                st.session_state.events = None
                st.session_state.heat_sheets = None
                st.session_state.timeline = None
                st.session_state.selected_swimmer = None
                st.session_state.swimmer_search_query = ""
                st.rerun()

    # ========================================================================
    # TAB 2: PREVIEW
    # ========================================================================
    with tab2:
        st.header("Event Preview")

        if st.session_state.events is None:
            st.info("Upload and parse a PDF first to see the preview.")
        else:
            st.markdown(f"### {len(events)} Events Found")
            # Check for low confidence entries

            low_conf_count = sum(1 for e in events for entry in e.entries if getattr(entry, "low_confidence", False))
            if low_conf_count > 0:
                st.warning(
                    f"⚠️ **Warning:** {low_conf_count} entries have been flagged as low-confidence due to potential parsing errors. "
                    "You can edit these entries directly in the tables below."
                )

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
                is_relay = event.entries and not hasattr(event.entries[0], "swimmer")
                with st.expander(
                    f"Event {event.event_label or event.number}: {event.gender} {event.distance}Y "
                    f"{event.stroke} ({len(event.entries)} entries)"
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Distance:** {event.distance} yards")
                    with col2:
                        st.markdown(f"**Stroke:** {event.stroke}")
                    with col3:
                        st.markdown(f"**Entries:** {len(event.entries)}")

                    st.markdown("**Editable Entries:**")
                    if is_relay:
                        rows = []
                        for entry in event.entries:
                            rows.append({
                                "Place": entry.place,
                                "Team Name": entry.team_name,
                                "Seed Time": entry.seed_time,
                                "Low Confidence": entry.low_confidence,
                                "Error Msg": entry.error_msg
                            })
                        import pandas as pd
                        df = pd.DataFrame(rows)
                        edited_df = st.data_editor(df, key=f"editor_{event.number}_{events.index(event)}", hide_index=True)
                        for i, row in edited_df.iterrows():
                            entry = event.entries[i]
                            entry.place = int(row["Place"])
                            entry.team_name = str(row["Team Name"])
                            entry.seed_time = str(row["Seed Time"])
                            entry.low_confidence = bool(row["Low Confidence"])
                            entry.error_msg = str(row["Error Msg"])
                    else:
                        rows = []
                        for entry in event.entries:
                            rows.append({
                                "Place": entry.place,
                                "Name": entry.swimmer.name,
                                "Age": entry.swimmer.age,
                                "Team Code": entry.swimmer.team_code,
                                "Seed Time": entry.seed_time,
                                "Low Confidence": entry.low_confidence,
                                "Error Msg": entry.error_msg
                            })
                        import pandas as pd
                        df = pd.DataFrame(rows)
                        edited_df = st.data_editor(df, key=f"editor_{event.number}_{events.index(event)}", hide_index=True)
                        for i, row in edited_df.iterrows():
                            entry = event.entries[i]
                            entry.place = int(row["Place"])
                            entry.seed_time = str(row["Seed Time"])
                            entry.low_confidence = bool(row["Low Confidence"])
                            entry.error_msg = str(row["Error Msg"])
                            entry.swimmer.name = str(row["Name"])
                            entry.swimmer.age = int(row["Age"]) if row["Age"] is not None and str(row["Age"]).isdigit() else None
                            entry.swimmer.team_code = str(row["Team Code"])


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
                    help=(
                        "Wall-clock time the meet begins, e.g. 8:00 AM. "
                        "Used as the single-session start when multi-session mode is off, "
                        "or as a fallback for events before the first defined session boundary."
                    ),
                )

            with col4:
                start_heat_number = st.number_input(
                    "Session Begins at Heat #:",
                    min_value=1,
                    max_value=50,
                    value=int(st.session_state.start_heat_number),
                    step=1,
                    help=(
                        "Heat number in the first event where the session clock starts. "
                        "Use 1 for a full-session estimate."
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
                "NT (no-time) heats default to 2 min for events ≤400Y, "
                "or 5 min for longer events."
            )

            # Persist base settings immediately
            st.session_state.meet_title = meet_title
            st.session_state.meet_date = meet_date
            st.session_state.num_lanes = num_lanes
            st.session_state.meet_start_time = meet_start_time
            st.session_state.start_heat_number = start_heat_number
            st.session_state.heat_gap_minutes = heat_gap_minutes

            # ----------------------------------------------------------------
            # Multi-Session Configuration
            # ----------------------------------------------------------------
            st.markdown("---")
            st.markdown("### Multi-Session Configuration")
            st.caption(
                "Define named sessions (e.g. Morning / Afternoon) with independent "
                "wall-clock start times. Heat numbers stay continuous across all sessions — "
                "only the clock resets. Inter-session gaps (lunch, warmup) are implicit."
            )

            multi_session = st.toggle(
                "Enable Multi-Session Mode",
                value=st.session_state.multi_session_mode,
                key="multi_session_toggle",
            )
            st.session_state.multi_session_mode = multi_session

            if multi_session:
                if st.button("➕ Add Session", key="add_session_btn"):
                    n = len(st.session_state.sessions) + 1
                    # Default start_event_num: offset from the last defined session
                    if st.session_state.sessions:
                        last_event_num = max(
                            s["start_event_num"] for s in st.session_state.sessions
                        )
                        default_event = last_event_num + 10
                    else:
                        default_event = 1
                    default_time = "8:00 AM" if n == 1 else "1:00 PM"
                    st.session_state.sessions.append({
                        "session_name": f"Session {n}",
                        "start_time": default_time,
                        "start_event_num": default_event,
                    })
                    st.rerun()

                if st.session_state.sessions:
                    # Column headers
                    hc1, hc2, hc3, hc4 = st.columns([3, 2, 2, 1])
                    with hc1:
                        st.markdown("**Session Name**")
                    with hc2:
                        st.markdown("**Wall-Clock Start**")
                    with hc3:
                        st.markdown("**First Event #**")
                    with hc4:
                        st.markdown("**Del**")

                    delete_idx = None
                    for i, session in enumerate(st.session_state.sessions):
                        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                        with c1:
                            st.session_state.sessions[i]["session_name"] = st.text_input(
                                "Session Name",
                                value=session["session_name"],
                                key=f"sname_{i}",
                                label_visibility="collapsed",
                            )
                        with c2:
                            st.session_state.sessions[i]["start_time"] = st.text_input(
                                "Start Time",
                                value=session["start_time"],
                                key=f"stime_{i}",
                                label_visibility="collapsed",
                                help="e.g. 9:00 AM or 1:30 PM",
                            )
                        with c3:
                            st.session_state.sessions[i]["start_event_num"] = st.number_input(
                                "Start Event #",
                                value=int(session["start_event_num"]),
                                min_value=1,
                                step=1,
                                key=f"sevent_{i}",
                                label_visibility="collapsed",
                            )
                        with c4:
                            if st.button("🗑️", key=f"sdel_{i}", help="Remove this session"):
                                delete_idx = i

                    # Deferred delete — avoids mid-loop index mutation
                    if delete_idx is not None:
                        st.session_state.sessions.pop(delete_idx)
                        st.rerun()

                    # Validation: duplicate start_event_num check
                    event_nums = [s["start_event_num"] for s in st.session_state.sessions]
                    if len(event_nums) != len(set(event_nums)):
                        st.warning(
                            "⚠️ Two or more sessions share the same start event number. "
                            "Resolve before generating."
                        )

                    # Session coverage summary
                    st.markdown("**Session Coverage:**")
                    sorted_sessions = sorted(
                        st.session_state.sessions, key=lambda s: s["start_event_num"]
                    )
                    total_events = len(st.session_state.events)
                    for idx, s in enumerate(sorted_sessions):
                        if idx + 1 < len(sorted_sessions):
                            end_label = f"Event {sorted_sessions[idx + 1]['start_event_num'] - 1}"
                        else:
                            end_label = f"Event {total_events} (end)"
                        st.markdown(
                            f"- **{s['session_name']}** — starts {s['start_time']}, "
                            f"Events {s['start_event_num']}–{end_label}"
                        )

                else:
                    st.info(
                        "No sessions defined yet. Click **➕ Add Session** to get started."
                    )

            else:
                # Multi-session off — surface any lingering definitions so they're visible
                if st.session_state.sessions:
                    st.caption(
                        f"ℹ️ {len(st.session_state.sessions)} session(s) are defined but "
                        "multi-session mode is off — they will be ignored at generation time."
                    )
                    if st.button("🗑️ Clear All Sessions", key="clear_sessions_btn"):
                        st.session_state.sessions = []
                        st.rerun()

            # ----------------------------------------------------------------
            # Current Settings Summary
            # ----------------------------------------------------------------
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
                if multi_session and st.session_state.sessions:
                    first_s = min(
                        st.session_state.sessions, key=lambda s: s["start_event_num"]
                    )
                    st.markdown(f"**Start:** {first_s['start_time']} *(S1)*")
                else:
                    st.markdown(f"**Start:** {meet_start_time}")
            with col_e:
                if multi_session and st.session_state.sessions:
                    st.markdown(f"**Sessions:** {len(st.session_state.sessions)}")
                else:
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

            session_mode_label = (
                f"{len(st.session_state.sessions)} sessions defined"
                if st.session_state.get("multi_session_mode") and st.session_state.get("sessions")
                else "Single session"
            )

            st.markdown(f"""
            ### Ready to Generate Heat Sheets

            **Configuration:**
            - Meet: {meet_title}
            - Date: {meet_date}
            - Lanes: {num_lanes}
            - Events: {len(events)}
            - Total Entries: {sum(len(e.entries) for e in events)}
            - Session Mode: {session_mode_label}
            - Session Start: {meet_start} (Heat {start_heat})
            - Heat Gap: {heat_gap} min
            """)

            if st.button(
                "Generate Heat Sheets", type="primary",
                width='stretch', key="generate_btn"
            ):
                heat_sheets = seed_all_events(events, num_lanes)

                if heat_sheets:
                    st.session_state.heat_sheets = heat_sheets

                    # Build SessionConfig list if multi-session mode is active
                    sessions_configs = None
                    if st.session_state.get("multi_session_mode") and st.session_state.get("sessions"):
                        sessions_configs = [
                            SessionConfig(
                                session_name=s["session_name"],
                                start_time=s["start_time"],
                                start_event_num=s["start_event_num"],
                            )
                            for s in st.session_state.sessions
                        ]

                    # Compute timeline immediately after seeding
                    timeline = estimate_meet_timeline(
                        heat_sheets,
                        gap_minutes=heat_gap,
                        meet_start_time=meet_start,
                        start_heat_number=start_heat,
                        sessions=sessions_configs,
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
                                f"**Event {event.event_label or event.number}: {event.gender} "
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
                st.caption(f"📁 Saves to: `{get_downloads_folder()}`")

                timeline = st.session_state.get("timeline")
                safe_title = sanitize_file_name(meet_title)
                downloads = get_downloads_folder()

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "💾 Save Full Meet PDF",
                        width='stretch',
                        key="save_full_meet",
                        type="primary",
                    ):
                        with st.spinner("Generating full meet PDF..."):
                            try:
                                out_path = downloads / f"HeatSheet_{safe_title}.pdf"
                                generate_full_meet_pdf(
                                    st.session_state.heat_sheets,
                                    str(out_path),
                                    meet_title=meet_title,
                                    meet_date=meet_date,
                                    timeline=timeline,
                                )
                                st.success(f"✅ Saved: `{out_path.name}`")
                            except Exception as e:
                                st.error(f"Error: {e}")

                with col2:
                    page_count = len(st.session_state.heat_sheets) + 1
                    st.info(f"{page_count} pages | {len(st.session_state.heat_sheets)} events")

                st.markdown("**Individual Event Heat Sheets:**")
                cols = st.columns(min(4, len(st.session_state.heat_sheets)))
                for idx, heat_sheet in enumerate(
                    sorted(st.session_state.heat_sheets, key=lambda h: h.event.number)
                ):
                    event = heat_sheet.event
                    with cols[idx % len(cols)]:
                        if st.button(
                            f"Event {event.event_label or event.number}",
                            width='stretch',
                            key=f"save_event_{event.event_label or event.number}_{idx}",
                        ):
                            with st.spinner(f"Saving Event {event.event_label or event.number}..."):
                                try:
                                    lbl = event.event_label if event.event_label else f"{event.number:02d}"
                                    out_path = downloads / f"Event_{lbl}_Heatsheet.pdf"
                                    generate_heat_sheet_pdf(
                                        heat_sheet,
                                        str(out_path),
                                        meet_title=meet_title,
                                        meet_date=meet_date,
                                        timeline=timeline,
                                    )
                                    st.success(f"✅ `{out_path.name}`")
                                except Exception as e:
                                    st.error(f"Error: {e}")

    # ========================================================================
    # TAB 5: FIND SWIMMER
    # ========================================================================
    with tab5:
        st.header("Find Swimmer")

        if st.session_state.heat_sheets is None:
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
                        st.dataframe(df, width='stretch', hide_index=True)

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
    with st.expander("💡 Tips"):
        st.markdown("""
        1. Upload a USA Swimming psych sheet PDF
        2. Check the preview to verify parsing
        3. Customize settings (meet name, date, lanes, timeline gap)
        4. Generate heat sheets — estimated meet duration is shown automatically
        5. Use Find Swimmer to look up any athlete's heat, lane, and start time
        6. Download as PDF for printing at meets
        """)


if __name__ == "__main__":
    main()