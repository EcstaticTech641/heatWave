#!/usr/bin/env python
"""
Desktop launcher for heatWave.

Starts the Streamlit application and hosts it in a native pywebview window.
Automatically finds a free port if 8501 is already in use, and waits for the
server to be ready before opening the window.

Usage:
    python run_desktop.py          # development
    dist/heatWave/heatWave.exe     # packaged
"""
import sys
import os
import threading
import socket
import signal
import time
import urllib.request
import webview

APP_VERSION = "1.0.0"
DEFAULT_PORT = 8501
MAX_WAIT_SECONDS = 30  # maximum time to wait for Streamlit to start


def _resolve_paths():
    """Set the working directory correctly for both dev and frozen modes."""
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        os.chdir(app_dir)
        internal_dir = os.path.join(app_dir, '_internal')
        if internal_dir not in sys.path:
            sys.path.insert(0, internal_dir)
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)


def _find_free_port(start: int = DEFAULT_PORT) -> int:
    """Return the first available TCP port starting from `start`."""
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find a free port in range "
                       f"{start}–{start + 19}. Close some applications and try again.")


def _wait_for_server(port: int, timeout: int = MAX_WAIT_SECONDS) -> bool:
    """Poll localhost:<port> until Streamlit responds or timeout is reached."""
    url = f"http://localhost:{port}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.25)
    return False


def _start_streamlit(app_path: str, port: int):
    """Run streamlit in a background thread."""
    # Streamlit calls signal.signal() internally which crashes on non-main
    # threads on Windows — patch it out for the duration of startup.
    original_signal = signal.signal
    signal.signal = lambda *args, **kwargs: None

    try:
        from streamlit.web import cli as stcli
        sys.argv = [
            "streamlit",
            "run",
            app_path,
            "--server.headless=true",
            f"--server.port={port}",
        ]
        stcli.main()
    except SystemExit:
        pass
    finally:
        signal.signal = original_signal


def main():
    _resolve_paths()

    # Resolve the path to the Streamlit UI script
    if getattr(sys, 'frozen', False):
        app_path = os.path.join(os.path.dirname(sys.executable),
                                "src", "ui", "streamlit_app.py")
    else:
        app_path = os.path.join("src", "ui", "streamlit_app.py")

    # --- Streamlit first-run configuration ---
    # Write credentials.toml to skip the first-launch email prompt
    credentials_dir = os.path.expanduser("~/.streamlit")
    os.makedirs(credentials_dir, exist_ok=True)
    credentials_file = os.path.join(credentials_dir, "credentials.toml")
    if not os.path.exists(credentials_file):
        with open(credentials_file, "w") as f:
            f.write('[general]\nemail = ""\n')

    # Suppress usage stats prompt via environment variable as a fallback
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    # --- Port selection ---
    port = _find_free_port(DEFAULT_PORT)

    # --- Start Streamlit in a background daemon thread ---
    t = threading.Thread(target=_start_streamlit, args=(app_path, port),
                         daemon=True)
    t.start()

    # --- Wait until the server is accepting connections ---
    ready = _wait_for_server(port, timeout=MAX_WAIT_SECONDS)
    if not ready:
        # Open anyway and let the user see an error in the webview
        pass

    # --- Open the native desktop window ---
    webview.create_window(
        f'heatWave v{APP_VERSION} — Heat Sheet Generator',
        f'http://localhost:{port}',
        width=1100,
        height=780,
        min_size=(800, 600),
    )
    webview.start()   # blocks until the window is closed


if __name__ == '__main__':
    main()
