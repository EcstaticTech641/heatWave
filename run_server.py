#!/usr/bin/env python
"""
Production server entry point for heatWave.
Uses Waitress to serve the Flask app.
"""
import os
import sys
import logging
from waitress import serve
from dotenv import load_dotenv

# Add the project root to the python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.ui.flask_app import app

def main():
    load_dotenv()
    
    # Configuration
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 8080))
    threads = int(os.environ.get('THREADS', 4))
    
    print(f"Starting heatWave production server on http://{host}:{port}")
    print(f"Threads: {threads}")
    
    # Suppress verbose logging if not in debug mode
    if os.environ.get('FLASK_DEBUG') != '1':
        logging.getLogger('waitress').setLevel(logging.INFO)
    
    try:
        serve(app, host=host, port=port, threads=threads)
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")

if __name__ == "__main__":
    main()
