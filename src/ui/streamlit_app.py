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
from src.utils.cleanup import start_cleanup_daemon, clear_directory, cleanup_old_files


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="heatWave - Heat Sheet Generator",
    page_icon="🏊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
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
    </style>
""", unsafe_allow_html=True)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def initialize_session_state():
    """Initialize session state variables."""
    if 'pdf_uploaded' not in st.session_state:
        st.session_state.pdf_uploaded = False
    if 'events' not in st.session_state:
        st.session_state.events = None
    if 'heat_sheets' not in st.session_state:
        st.session_state.heat_sheets = None
    if 'pdf_content' not in st.session_state:
        st.session_state.pdf_content = None
    if 'cleanup_daemon' not in st.session_state:
        # Start background cleanup daemon for data/output directory
        # Cleans files older than 1 hour every 5 minutes
        st.session_state.cleanup_daemon = start_cleanup_daemon(
            "data/output",
            check_interval_minutes=5,
            max_age_hours=1
        )


def process_pdf(pdf_file):
    """Process uploaded PDF and extract events."""
    try:
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_file.getbuffer())
            tmp_path = tmp_file.name
        
        # Extract and parse
        with st.spinner("📖 Extracting text from PDF..."):
            text = extract_text_from_pdf(tmp_path)
        
        with st.spinner("🔍 Parsing events and entries..."):
            events = parse_events_from_text(text)
        
        # Clean up
        Path(tmp_path).unlink()
        
        return events, text
    
    except Exception as e:
        st.error(f"❌ Error processing PDF: {str(e)}")
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
        st.error(f"❌ Error seeding events: {str(e)}")
        return None


def generate_pdfs(heat_sheets, meet_title, meet_date, num_lanes):
    """Generate PDF files."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Generate full meet PDF
            with st.spinner("📄 Generating complete meet PDF..."):
                full_pdf_path = tmpdir / "Full_Meet_Heatsheets.pdf"
                generate_full_meet_pdf(
                    heat_sheets,
                    str(full_pdf_path),
                    meet_title=meet_title,
                    meet_date=meet_date
                )
                
                # Read PDF content
                with open(full_pdf_path, 'rb') as f:
                    full_pdf_content = f.read()
            
            # Generate individual event PDFs
            individual_pdfs = {}
            with st.spinner("📄 Generating individual event PDFs..."):
                for heat_sheet in heat_sheets:
                    event = heat_sheet.event
                    pdf_path = tmpdir / f"Event_{event.number:02d}_Heatsheet.pdf"
                    
                    generate_heat_sheet_pdf(
                        heat_sheet,
                        str(pdf_path),
                        meet_title=meet_title,
                        meet_date=meet_date
                    )
                    
                    with open(pdf_path, 'rb') as f:
                        individual_pdfs[event.number] = f.read()
            
            return full_pdf_content, individual_pdfs
    
    except Exception as e:
        st.error(f"❌ Error generating PDFs: {str(e)}")
        return None, None


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    initialize_session_state()
    
    # Header
    st.markdown('<div class="main-header">🏊 heatWave</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Psych Sheet to Heat Sheet Converter</div>', unsafe_allow_html=True)
    
    # ========================================================================
    # SIDEBAR: ADMIN & CLEANUP
    # ========================================================================
    with st.sidebar:
        st.markdown("### ⚙️ Admin")
        
        if st.button("🗑️ Clear All Generated Files", use_container_width=True, type="secondary"):
            cleared = clear_directory("data/output")
            st.success(f"✅ Cleared {cleared} PDF file(s) from data/output/")
        
        st.caption("""
        **Auto-cleanup enabled:**
        - Files older than 1 hour are automatically deleted
        - Check runs every 5 minutes
        - Use button above for manual cleanup
        """)
        
        st.divider()
        
        st.markdown("### 🔒 Security")
        st.info("""
        **Zero-Persistent-Storage Design:**
        - Temp folders auto-delete after each generation
        - PDFs loaded into memory for download only
        - No user data stored server-side
        """)
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "👀 Preview", "⚙️ Settings", "📊 Generate"])
    
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
                label_visibility="collapsed"
            )
            
            if uploaded_file is not None:
                st.session_state.pdf_uploaded = True
                
                st.markdown('<div class="success-box">✅ PDF uploaded successfully!</div>', unsafe_allow_html=True)
                
                st.info(f"File: **{uploaded_file.name}**")
                st.info(f"Size: **{uploaded_file.size / 1024:.1f} KB**")
                
                # Process PDF
                if st.button("🔍 Parse PDF", type="primary", use_container_width=True):
                    events, text = process_pdf(uploaded_file)
                    
                    if events:
                        st.session_state.events = events
                        st.session_state.pdf_uploaded = True
                        
                        # Show success message
                        st.markdown('<div class="success-box">✅ PDF parsed successfully!</div>', unsafe_allow_html=True)
                        
                        # Quick stats
                        relay_count = sum(1 for e in events if e.entries and not hasattr(e.entries[0], 'swimmer'))
                        individual_count = sum(1 for e in events if e.entries and hasattr(e.entries[0], 'swimmer'))
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
                        
                        st.success("✅ Ready to seed heats! Go to the **Settings** tab to customize.")
        
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
            st.info("📤 Upload and parse a PDF first to see the preview.")
        else:
            events = st.session_state.events
            
            st.markdown(f"### {len(events)} Events Found")
            
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                event_type_filter = st.selectbox(
                    "Filter by type:",
                    ["All", "Individual", "Relay"]
                )
            
            with col2:
                search_query = st.text_input("Search event name:", "")
            
            # Filter events
            filtered_events = events
            if event_type_filter != "All":
                filtered_events = [
                    e for e in filtered_events
                    if ((event_type_filter == "Individual" and e.entries and hasattr(e.entries[0], 'swimmer')) or
                        (event_type_filter == "Relay" and e.entries and not hasattr(e.entries[0], 'swimmer')))
                ]
            
            if search_query:
                filtered_events = [e for e in filtered_events if search_query.lower() in e.name.lower()]
            
            # Display events
            for event in filtered_events[:10]:  # Show first 10
                with st.expander(f"Event {event.number}: {event.gender} {event.distance}Y {event.stroke} ({len(event.entries)} entries)"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Distance:** {event.distance} yards")
                    with col2:
                        st.markdown(f"**Stroke:** {event.stroke}")
                    with col3:
                        st.markdown(f"**Entries:** {len(event.entries)}")
                    
                    # Show sample entries
                    st.markdown("**Sample Entries:**")
                    for entry in event.entries[:5]:
                        if hasattr(entry, 'swimmer'):
                            st.markdown(f"- {entry.swimmer.name} ({entry.swimmer.age}yo, {entry.swimmer.team_code}) - {entry.seed_time}")
                        else:
                            st.markdown(f"- {entry.team_name} - {entry.seed_time}")
                    
                    if len(event.entries) > 5:
                        st.caption(f"... and {len(event.entries) - 5} more entries")
            
            if len(filtered_events) > 10:
                st.caption(f"Showing first 10 of {len(filtered_events)} events. Use filters to narrow down.")
    
    # ========================================================================
    # TAB 3: SETTINGS
    # ========================================================================
    with tab3:
        st.header("Heat Sheet Settings")
        
        if st.session_state.events is None:
            st.info("📤 Upload and parse a PDF first to configure settings.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Meet Information")
                meet_title = st.text_input(
                    "Meet Title:",
                    value="Swimming Meet",
                    help="Display name for the meet"
                )
                meet_date = st.text_input(
                    "Meet Date:",
                    value=datetime.now().strftime("%m/%d/%Y"),
                    help="Date to display on heat sheets (format: MM/DD/YYYY)"
                )
            
            with col2:
                st.markdown("### Pool Configuration")
                num_lanes = st.number_input(
                    "Number of Lanes:",
                    min_value=4,
                    max_value=10,
                    value=8,
                    step=1,
                    help="Typical: 8 lanes"
                )
                
                st.markdown("*Note: Seeding follows USA Swimming rules*")
            
            # Preview settings
            st.markdown("---")
            st.markdown("### Preview Settings")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Meet:** {meet_title}")
            with col2:
                st.markdown(f"**Date:** {meet_date}")
            with col3:
                st.markdown(f"**Lanes:** {num_lanes}")
            
            # Store settings in session state
            st.session_state.meet_title = meet_title
            st.session_state.meet_date = meet_date
            st.session_state.num_lanes = num_lanes
    
    # ========================================================================
    # TAB 4: GENERATE
    # ========================================================================
    with tab4:
        st.header("Generate Heat Sheets")
        
        if st.session_state.events is None:
            st.warning("⚠️ Please upload and parse a PDF first.")
        else:
            # Get settings from session state
            meet_title = st.session_state.get('meet_title', 'Swimming Meet')
            meet_date = st.session_state.get('meet_date', datetime.now().strftime("%m/%d/%Y"))
            num_lanes = st.session_state.get('num_lanes', 8)
            
            events = st.session_state.events
            
            st.markdown(f"""
            ### Ready to Generate Heat Sheets
            
            **Configuration:**
            - Meet: {meet_title}
            - Date: {meet_date}
            - Lanes: {num_lanes}
            - Events: {len(events)}
            - Total Entries: {sum(len(e.entries) for e in events)}
            """)
            
            # Main generate button
            if st.button("🚀 Generate Heat Sheets", type="primary", use_container_width=True, key="generate_btn"):
                # Seed all events
                heat_sheets = seed_all_events(events, num_lanes)
                
                if heat_sheets:
                    st.session_state.heat_sheets = heat_sheets
                    
                    # Show stats
                    st.markdown('<div class="success-box">✅ Events seeded successfully!</div>', unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Heats", sum(h.heats for h in heat_sheets))
                    with col2:
                        st.metric("Avg Entries/Heat", f"{sum(len(h.assignments) for h in heat_sheets) / sum(h.heats for h in heat_sheets):.1f}")
                    with col3:
                        largest = max(heat_sheets, key=lambda h: len(h.assignments))
                        st.metric("Largest Event", f"{len(largest.assignments)} entries")
                    with col4:
                        smallest = min(heat_sheets, key=lambda h: len(h.assignments))
                        st.metric("Smallest Event", f"{len(smallest.assignments)} entries")
                    
                    # Display heat distribution
                    with st.expander("📊 View Heat Details"):
                        for heat_sheet in heat_sheets[:5]:
                            event = heat_sheet.event
                            st.markdown(f"**Event {event.number}: {event.gender} {event.distance}Y {event.stroke}**")
                            
                            heats_by_num = {}
                            for assignment in heat_sheet.assignments:
                                heat_num = assignment.heat
                                if heat_num not in heats_by_num:
                                    heats_by_num[heat_num] = []
                                heats_by_num[heat_num].append(assignment)
                            
                            heat_sizes = [len(heats_by_num.get(h, [])) for h in range(1, heat_sheet.heats + 1)]
                            st.markdown(f"- Heats: {heat_sheet.heats} | Distribution: {heat_sizes}")
                        
                        if len(heat_sheets) > 5:
                            st.caption(f"... and {len(heat_sheets) - 5} more events")
            
            # Download section
            if st.session_state.heat_sheets:
                st.markdown("---")
                st.markdown("### 📥 Download Heat Sheets")
                
                # Generate PDFs
                full_pdf, individual_pdfs = generate_pdfs(
                    st.session_state.heat_sheets,
                    meet_title,
                    meet_date,
                    num_lanes
                )
                
                if full_pdf:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.download_button(
                            label="📄 Download Full Meet PDF",
                            data=full_pdf,
                            file_name=f"HeatSheet_{meet_title.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    
                    with col2:
                        st.info(f"📄 File size: {len(full_pdf) / 1024:.1f} KB | {len(st.session_state.heat_sheets) + 1} pages")
                    
                    # Individual event downloads
                    if individual_pdfs:
                        st.markdown("**Individual Event Heat Sheets:**")
                        
                        cols = st.columns(min(4, len(individual_pdfs)))
                        for idx, (event_num, pdf_content) in enumerate(sorted(individual_pdfs.items())):
                            with cols[idx % len(cols)]:
                                st.download_button(
                                    label=f"Event {event_num}",
                                    data=pdf_content,
                                    file_name=f"Event_{event_num:02d}_Heatsheet.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"download_event_{event_num}"
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
    <br>3. Customize settings (meet name, date, lanes)
    <br>4. Generate heat sheets with USA Swimming seeding rules
    <br>5. Download as PDF for printing at meets
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("📧 Questions? Report bugs to the development team.")
    with col2:
        st.caption("🏊 Made for USA Swimming coaches")
    with col3:
        st.caption(f"Last updated: {datetime.now().strftime('%m/%d/%Y')}")


if __name__ == "__main__":
    main()
