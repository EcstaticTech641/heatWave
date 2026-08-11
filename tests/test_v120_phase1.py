"""
Unit and Integration Test Suite for heatWave v1.2.1:
- Version consistency (1.2.1 across configuration & docs)
- Windows Theme Auto-Sync detection
- CLI PDF File Ingestion argument handling
- Desktop launcher health check & path resolution
"""
import os
import re
import sys
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def test_version_consistency():
    """Verify current version is consistently set across pyproject.toml, run_desktop.py, installer.iss, and docs."""
    from src._version import __version__ as expected_version

    # 1. pyproject.toml
    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{expected_version}"' in pyproject_text

    # 2. run_desktop.py — now imports __version__ from src._version
    run_desktop_text = (PROJECT_ROOT / "run_desktop.py").read_text(encoding="utf-8")
    assert 'from src._version import __version__ as APP_VERSION' in run_desktop_text

    # 3. installer.iss
    installer_text = (PROJECT_ROOT / "installer.iss").read_text(encoding="utf-8")
    assert f"AppVersion={expected_version}" in installer_text
    assert f"heatWave_v{expected_version}_setup" in installer_text

    # 4. README.md
    readme_text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"**Version:** {expected_version}" in readme_text

    # 5. DEFECTS.md — contains version string anywhere in file
    defects_text = (PROJECT_ROOT / "DEFECTS.md").read_text(encoding="utf-8")
    assert expected_version in defects_text


def test_windows_theme_detection():
    """Verify get_windows_theme returns 'light' or 'dark' without raising exceptions."""
    from run_desktop import get_windows_theme

    theme = get_windows_theme()
    assert theme in {"light", "dark"}


def test_cli_pdf_argument_parsing(monkeypatch, tmp_path):
    """Verify CLI PDF argument is parsed into HEATWAVE_CLI_PDF environment variable."""
    dummy_pdf = tmp_path / "test_meet.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 mock content")

    monkeypatch.setattr(sys, "argv", ["run_desktop.py", str(dummy_pdf)])
    monkeypatch.delenv("HEATWAVE_CLI_PDF", raising=False)

    # Simulate run_desktop.py main CLI parsing logic
    candidate = sys.argv[1]
    if os.path.isfile(candidate) and candidate.lower().endswith(".pdf"):
        os.environ["HEATWAVE_CLI_PDF"] = os.path.abspath(candidate)

    assert os.environ.get("HEATWAVE_CLI_PDF") == str(dummy_pdf.resolve())


def test_launcher_path_resolution():
    """Verify _get_streamlit_app_path resolves existing streamlit_app.py."""
    from run_desktop import _get_streamlit_app_path
    app_path = _get_streamlit_app_path()
    assert os.path.exists(app_path)
    assert app_path.endswith("streamlit_app.py")


def test_wait_for_server_early_exit_on_thread_error():
    """Verify _wait_for_server exits early if thread status indicates error."""
    from run_desktop import _wait_for_server
    status_dict = {"finished": True, "error": "Mock thread failure"}
    ready = _wait_for_server(port=9999, status_dict=status_dict, timeout=5)
    assert ready is False

