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

APP_VERSION = "1.2.1"
DEFAULT_PORT = 8501
MAX_WAIT_SECONDS = 30  # maximum time to wait for Streamlit to start


def get_windows_theme() -> str:
    """Detect Windows system color theme (light vs dark) using winreg."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return "light"


def _log(msg: str):
    """Write timestamped launcher events to ~/.streamlit/heatwave_launcher.log."""
    try:
        log_dir = os.path.expanduser("~/.streamlit")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "heatwave_launcher.log"), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


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
        _log(f"Frozen mode initialized. app_dir={app_dir}, internal_dir={internal_dir}")
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        _log(f"Dev mode initialized. project_root={project_root}")


def _get_streamlit_app_path() -> str:
    """Resolve the absolute path to streamlit_app.py across bundle layouts."""
    candidates = []
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        app_dir = os.path.dirname(sys.executable)
        if meipass:
            candidates.append(os.path.join(meipass, "src", "ui", "streamlit_app.py"))
        candidates.append(os.path.join(app_dir, "_internal", "src", "ui", "streamlit_app.py"))
        candidates.append(os.path.join(app_dir, "src", "ui", "streamlit_app.py"))
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(project_root, "src", "ui", "streamlit_app.py"))
        candidates.append(os.path.join("src", "ui", "streamlit_app.py"))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            resolved = os.path.abspath(candidate)
            _log(f"Resolved app_path: {resolved}")
            return resolved

    fallback = candidates[0] if candidates else os.path.join("src", "ui", "streamlit_app.py")
    _log(f"WARNING: Preferred candidates missing. Falling back to: {fallback}")
    return fallback


def _find_free_port(start: int = DEFAULT_PORT) -> int:
    """Return the first available TCP port starting from `start`."""
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                _log(f"Bound free port: {port}")
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find a free port in range "
                       f"{start}–{start + 19}. Close some applications and try again.")


def _wait_for_server(port: int, status_dict: dict, timeout: int = MAX_WAIT_SECONDS) -> bool:
    """Poll 127.0.0.1:<port> until Streamlit responds or timeout is reached."""
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    base_url = f"http://127.0.0.1:{port}/"
    deadline = time.time() + timeout

    _log(f"Polling server at {health_url} (timeout={timeout}s)...")
    while time.time() < deadline:
        # If server thread crashed or terminated early, stop waiting
        if status_dict.get("finished") and "error" in status_dict:
            _log(f"Streamlit thread died prematurely: {status_dict.get('error')}")
            return False

        for target in (health_url, base_url):
            try:
                req = urllib.request.Request(target, headers={'User-Agent': 'heatWave-Desktop-Launcher'})
                with urllib.request.urlopen(req, timeout=1.0) as response:
                    if response.status in (200, 302, 304, 404):
                        _log(f"Server is healthy (HTTP {response.status}) on port {port}.")
                        return True
            except urllib.error.HTTPError as err:
                _log(f"Server responded with HTTP {err.code} on port {port}.")
                if err.code in (200, 302, 304, 404):
                    return True
            except Exception:
                pass
        time.sleep(0.25)
    _log(f"Server health check timed out after {timeout}s on port {port}.")
    return False


def _ensure_streamlit_metadata():
    """Ensure importlib.metadata.version('streamlit') succeeds in frozen executables."""
    try:
        import importlib.metadata
        orig_version = importlib.metadata.version

        def safe_version(pkg_name: str) -> str:
            try:
                return orig_version(pkg_name)
            except importlib.metadata.PackageNotFoundError:
                if pkg_name.lower() in ("streamlit", "fitz", "reportlab", "pdfplumber", "pydantic"):
                    return "1.40.0"
                raise

        importlib.metadata.version = safe_version
    except Exception:
        pass


def _start_streamlit(app_path: str, port: int, status_dict: dict):
    """Run streamlit in a background thread and record any startup errors."""
    original_signal = signal.signal
    signal.signal = lambda *args, **kwargs: None
    _ensure_streamlit_metadata()

    try:
        from streamlit.web import cli as stcli
        sys.argv = [
            "streamlit",
            "run",
            app_path,
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
        ]
        _log(f"Starting Streamlit CLI thread with args: {sys.argv}")
        stcli.main()
    except SystemExit as exc:
        _log(f"Streamlit CLI SystemExit: {exc}")
    except Exception as exc:
        _log(f"Streamlit CLI Exception: {exc}")
        status_dict["error"] = str(exc)
    finally:
        signal.signal = original_signal
        status_dict["finished"] = True


def main():
    _resolve_paths()

    # --- CLI PDF Ingestion ---
    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if os.path.isfile(candidate) and candidate.lower().endswith(".pdf"):
            os.environ["HEATWAVE_CLI_PDF"] = os.path.abspath(candidate)

    # --- Windows Dark Mode Auto-Sync ---
    os.environ["STREAMLIT_THEME_BASE"] = get_windows_theme()

    # Resolve the path to the Streamlit UI script
    app_path = _get_streamlit_app_path()

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
    status_dict = {}
    t = threading.Thread(
        target=_start_streamlit,
        args=(app_path, port, status_dict),
        daemon=True
    )
    t.start()

    # --- Wait until the server is accepting connections ---
    ready = _wait_for_server(port, status_dict, timeout=MAX_WAIT_SECONDS)
    if not ready:
        err_detail = status_dict.get("error", "Streamlit server failed to start within the timeout period.")
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>heatWave — Startup Error</title></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 32px; line-height: 1.5;">
            <div style="max-width: 540px; margin: 0 auto; background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 24px;">
                <h2 style="color: #f87171; margin-top: 0;">heatWave Startup Error</h2>
                <p>The local Streamlit web server failed to initialize on port <strong>{port}</strong>.</p>
                <div style="background: #090d16; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; color: #fbbf24; word-break: break-all;">
                    {err_detail}
                </div>
                <p style="margin-bottom: 0; color: #94a3b8; font-size: 14px;">Please close any conflicting applications on port {port} and restart heatWave.</p>
            </div>
        </body>
        </html>
        """
        webview.create_window(
            'heatWave — Startup Error',
            html=error_html,
            width=640,
            height=420,
            resizable=False
        )
        webview.start()
        sys.exit(1)

    # --- Open the native desktop window ---
    webview.create_window(
        f'heatWave v{APP_VERSION} — Heat Sheet Generator',
        f'http://127.0.0.1:{port}',
        width=1100,
        height=780,
        min_size=(800, 600),
    )
    webview.start()   # blocks until the window is closed


if __name__ == '__main__':
    main()

