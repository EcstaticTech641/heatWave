#!/usr/bin/env python
"""
Desktop launcher for heatWave.

Opens the Flask-based UI inside a native desktop window (pywebview).
Works both as a regular Python script and as a PyInstaller .exe.

Usage:
    python run_desktop.py          # development
    dist/heatWave/heatWave.exe     # packaged
"""
import sys
import os
import threading
import logging

# Suppress noisy logs when running as a desktop app
logging.getLogger('werkzeug').setLevel(logging.WARNING)


def _resolve_paths():
    """Set the working directory correctly for both dev and frozen modes."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller .exe — chdir to the exe's folder
        app_dir = os.path.dirname(sys.executable)
        os.chdir(app_dir)

        # Ensure the project root is importable (for `from src.…` imports)
        internal_dir = os.path.join(app_dir, '_internal')
        if internal_dir not in sys.path:
            sys.path.insert(0, internal_dir)
    else:
        # Running as script — make sure project root is on sys.path
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)


def _start_flask(host='127.0.0.1', port=5000):
    """Start the Flask server in a background thread."""
    from src.ui.flask_app import app
    app.run(host=host, port=port, debug=False, use_reloader=False)


def main():
    _resolve_paths()

    host = '127.0.0.1'
    port = 5000

    # Start Flask in a daemon thread so it dies with the main process
    server_thread = threading.Thread(
        target=_start_flask,
        args=(host, port),
        daemon=True,
    )
    server_thread.start()

    # Open native desktop window via pywebview
    try:
        import webview
        window = webview.create_window(
            'heatWave — Heat Sheet Generator',
            f'http://{host}:{port}',
            width=1100,
            height=780,
            min_size=(800, 600),
        )
        webview.start()   # blocks until window is closed
    except ImportError:
        # pywebview not installed — fall back to browser
        import webbrowser
        import time
        print(f'heatWave is running at http://{host}:{port}')
        print('   Opening your browser…')
        time.sleep(1)
        webbrowser.open(f'http://{host}:{port}')
        print('   Close this window to stop the server.\n')
        try:
            server_thread.join()   # keep alive
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
