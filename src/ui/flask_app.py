"""
heatWave Flask backend — lightweight replacement for Streamlit.
Provides JSON API routes for PDF upload, parsing, seeding, and generation.
Works both as a regular Python app and inside a PyInstaller .exe.
"""
import io
import sys
import os
import json
import math
import tempfile
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_file, render_template, session
from flask_session import Session
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

# ---------------------------------------------------------------------------
# Resolve paths for both dev and frozen (PyInstaller) mode
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    # Running as PyInstaller exe — _MEIPASS or _internal contains bundled data
    _BASE_DIR = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(os.path.dirname(sys.executable)) / '_internal'
    _TEMPLATE_DIR = _BASE_DIR / 'src' / 'ui' / 'templates'
else:
    _BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root
    _TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates'

app = Flask(__name__, template_folder=str(_TEMPLATE_DIR))
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload

# ---------------------------------------------------------------------------
# Configure Flask-Session (multi-user isolation)
# ---------------------------------------------------------------------------
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'heatwave-dev-secret-key-123')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = tempfile.gettempdir() + '/heatwave_sessions'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# Ensure the session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

Session(app)


# ---------------------------------------------------------------------------
# Import project modules (same ones Streamlit used)
# ---------------------------------------------------------------------------
from src.parser.extractor import extract_text_from_pdf, parse_events_from_text
from src.seeding.seeder import seed_event, format_heat_sheet
from src.core.pdf_generator import generate_full_meet_pdf, generate_heat_sheet_pdf
from src.models.schemas import Entry, RelayEntry


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    """Serve the single-page UI."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """Upload and parse a psych-sheet PDF."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    pdf_file = request.files['file']
    if pdf_file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    try:
        # Save to a temp file, extract, then delete
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            pdf_file.save(tmp)
            tmp_path = tmp.name

        text = extract_text_from_pdf(tmp_path)
        events = parse_events_from_text(text)
        Path(tmp_path).unlink(missing_ok=True)

        # Store parsed events in session
        session['events'] = events
        session['heat_sheets'] = None  # reset any prior generation

        # Build a JSON-friendly summary
        events_summary = []
        for ev in events:
            entry_samples = []
            for e in ev.entries[:5]:
                if isinstance(e, Entry):
                    entry_samples.append({
                        'type': 'individual',
                        'name': e.swimmer.name,
                        'age': e.swimmer.age,
                        'team': e.swimmer.team_code,
                        'seed_time': e.seed_time,
                    })
                else:
                    entry_samples.append({
                        'type': 'relay',
                        'team': e.team_name,
                        'seed_time': e.seed_time,
                    })

            events_summary.append({
                'number': ev.number,
                'name': ev.name,
                'gender': ev.gender,
                'distance': ev.distance,
                'stroke': ev.stroke,
                'entry_count': len(ev.entries),
                'sample_entries': entry_samples,
            })

        total_entries = sum(len(ev.entries) for ev in events)

        return jsonify({
            'success': True,
            'filename': pdf_file.filename,
            'event_count': len(events),
            'total_entries': total_entries,
            'events': events_summary,
        })

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/generate', methods=['POST'])
def generate():
    """Seed events and generate heat sheets."""
    if session['events'] is None:
        return jsonify({'error': 'No events parsed yet. Upload a PDF first.'}), 400

    data = request.get_json(silent=True) or {}
    num_lanes = int(data.get('lanes', 8))

    try:
        heat_sheets = []
        for event in session['events']:
            if event.entries:
                hs = seed_event(event, lanes=num_lanes)
                heat_sheets.append(hs)

        session['heat_sheets'] = heat_sheets

        # Summary for the frontend
        summary = []
        for hs in heat_sheets:
            heats_by_num = {}
            for a in hs.assignments:
                heats_by_num.setdefault(a.heat, []).append(a)
            heat_sizes = [len(heats_by_num.get(h, [])) for h in range(1, hs.heats + 1)]

            summary.append({
                'event_number': hs.event.number,
                'event_name': f"{hs.event.gender} {hs.event.distance}Y {hs.event.stroke}",
                'heats': hs.heats,
                'entries': len(hs.assignments),
                'heat_distribution': heat_sizes,
            })

        total_heats = sum(hs.heats for hs in heat_sheets)
        total_entries = sum(len(hs.assignments) for hs in heat_sheets)

        return jsonify({
            'success': True,
            'total_heats': total_heats,
            'total_entries': total_entries,
            'events': summary,
        })

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/download/full', methods=['GET'])
def download_full_pdf():
    """Download the full meet heat-sheet PDF."""
    if session['heat_sheets'] is None:
        return jsonify({'error': 'No heat sheets generated yet.'}), 400

    meet_title = request.args.get('title', 'Swimming Meet')
    meet_date = request.args.get('date', datetime.now().strftime('%m/%d/%Y'))

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / 'Full_Meet_Heatsheets.pdf'
            generate_full_meet_pdf(
                session['heat_sheets'],
                str(pdf_path),
                meet_title=meet_title,
                meet_date=meet_date,
            )
            pdf_bytes = pdf_path.read_bytes()

        safe_title = meet_title.replace(' ', '_')
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'HeatSheet_{safe_title}.pdf',
        )

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/download/event/<int:event_num>', methods=['GET'])
def download_event_pdf(event_num):
    """Download the heat-sheet PDF for a single event."""
    if session['heat_sheets'] is None:
        return jsonify({'error': 'No heat sheets generated yet.'}), 400

    meet_title = request.args.get('title', 'Swimming Meet')
    meet_date = request.args.get('date', datetime.now().strftime('%m/%d/%Y'))

    hs = next((h for h in session['heat_sheets'] if h.event.number == event_num), None)
    if hs is None:
        return jsonify({'error': f'Event {event_num} not found.'}), 404

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / f'Event_{event_num:02d}_Heatsheet.pdf'
            generate_heat_sheet_pdf(
                hs,
                str(pdf_path),
                meet_title=meet_title,
                meet_date=meet_date,
            )
            pdf_bytes = pdf_path.read_bytes()

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Event_{event_num:02d}_Heatsheet.pdf',
        )

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/api/status', methods=['GET'])
def status():
    """Return current session status for the frontend."""
    has_events = session['events'] is not None
    has_heats = session['heat_sheets'] is not None
    return jsonify({
        'has_events': has_events,
        'has_heats': has_heats,
        'event_count': len(session['events']) if has_events else 0,
        'heat_sheet_count': len(session['heat_sheets']) if has_heats else 0,
    })


# ---------------------------------------------------------------------------
# Standalone usage (for development without pywebview)
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
