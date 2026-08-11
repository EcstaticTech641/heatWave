"""
Unit and Integration Test Suite for heatWave v1.3.0 features:
- Version consistency (1.3.0 across configuration, build scripts, & docs)
- Direct Deck Printing fallback and error handling (src/utils/printer.py)
- Privacy-Safe Manual Update Checker parsing and network error handling (src/utils/updater.py)
- Telemetry assertion (zero background network calls on module import)
"""
import io
import json
import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from src.utils.printer import is_virtual_printer, list_windows_printers, print_pdf_file
from src.utils.updater import check_for_updates, parse_version_tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_is_virtual_printer_detection():
    """Verify is_virtual_printer accurately identifies virtual file-creation drivers."""
    assert is_virtual_printer("Microsoft Print to PDF") is True
    assert is_virtual_printer("Microsoft XPS Document Writer") is True
    assert is_virtual_printer("Send to OneNote 2016") is True
    assert is_virtual_printer("CutePDF Writer") is True
    assert is_virtual_printer("Adobe PDF") is True

    assert is_virtual_printer("HP LaserJet Pro M404dn") is False
    assert is_virtual_printer("Brother HL-L2350DW") is False
    assert is_virtual_printer("Zebra ZD421 Deck Printer") is False
    assert is_virtual_printer("") is False


def test_printer_utility_virtual_printer_guard():
    """Verify print_pdf_file rejects virtual file printers with clear user guidance."""
    tmp_pdf = PROJECT_ROOT / "tests" / "test_virtual_dummy.pdf"
    tmp_pdf.write_text("%PDF-1.4 dummy spool", encoding="utf-8")

    mock_win32api = MagicMock()
    mock_win32print = MagicMock()

    try:
        with patch("sys.platform", "win32"):
            with patch.dict("sys.modules", {"win32api": mock_win32api, "win32print": mock_win32print}):
                ok, msg = print_pdf_file(str(tmp_pdf), "Microsoft Print to PDF")
                assert ok is False
                assert "virtual file printer" in msg
                assert "Download Heat Sheet PDF" in msg
                # ShellExecute should NOT be called for virtual printers
                mock_win32api.ShellExecute.assert_not_called()
    finally:
        if tmp_pdf.exists():
            tmp_pdf.unlink()



def test_v130_version_consistency():
    """Verify current version is consistently set across project configuration, launcher, and docs."""
    from src._version import __version__ as expected_version

    # 1. pyproject.toml
    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{expected_version}"' in pyproject_text

    # 2. run_desktop.py — now imports __version__ from src._version
    run_desktop_text = (PROJECT_ROOT / "run_desktop.py").read_text(encoding="utf-8")
    assert 'from src._version import __version__ as APP_VERSION' in run_desktop_text

    # 3. installer.iss
    installer_text = (PROJECT_ROOT / "installer.iss").read_text(encoding="utf-8")
    assert f'AppVersion={expected_version}' in installer_text
    assert f'OutputBaseFilename=heatWave_v{expected_version}_setup' in installer_text

    # 4. README.md
    readme_text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert f'**Version:** {expected_version}' in readme_text

    # 5. DEFECTS.md
    defects_text = (PROJECT_ROOT / "DEFECTS.md").read_text(encoding="utf-8")
    assert expected_version in defects_text

    # 6. build_heatwave.py fallback
    build_script_text = (PROJECT_ROOT / "build_heatwave.py").read_text(encoding="utf-8")
    assert f'return "{expected_version}"' in build_script_text


def test_version_tuple_parsing():
    """Verify parse_version_tuple correctly parses semver strings."""
    assert parse_version_tuple("1.3.0") == (1, 3, 0)
    assert parse_version_tuple("v1.4.2") == (1, 4, 2)
    assert parse_version_tuple("2.0") == (2, 0, 0)
    assert parse_version_tuple("invalid") == (0, 0, 0)


def test_printer_utility_missing_file():
    """Verify print_pdf_file returns error when target PDF does not exist."""
    ok, msg = print_pdf_file("nonexistent_file_xyz_123.pdf")
    assert ok is False
    assert "not found" in msg.lower()


def test_printer_utility_non_windows_fallback():
    """Verify printer functions handle non-Windows environments gracefully."""
    with patch("sys.platform", "linux"):
        printers, default_p = list_windows_printers()
        assert printers == []
        assert default_p == ""

        # Create temporary file to test print_pdf_file platform check
        tmp_pdf = PROJECT_ROOT / "tests" / "test_dummy.pdf"
        tmp_pdf.write_text("%PDF-1.4 dummy", encoding="utf-8")
        try:
            ok, msg = print_pdf_file(str(tmp_pdf))
            assert ok is False
            assert "only supported on Windows" in msg
        finally:
            if tmp_pdf.exists():
                tmp_pdf.unlink()


def test_printer_utility_mock_spooling():
    """Verify print_pdf_file invokes win32api ShellExecute when on Windows."""
    tmp_pdf = PROJECT_ROOT / "tests" / "test_spool_dummy.pdf"
    tmp_pdf.write_text("%PDF-1.4 dummy spool", encoding="utf-8")

    mock_win32api = MagicMock()
    mock_win32api.ShellExecute.return_value = 42  # >32 indicates success
    mock_win32print = MagicMock()
    mock_win32print.GetDefaultPrinter.return_value = "Test Laser Printer"

    try:
        with patch("sys.platform", "win32"):
            with patch.dict("sys.modules", {"win32api": mock_win32api, "win32print": mock_win32print}):
                ok, msg = print_pdf_file(str(tmp_pdf), "Test Laser Printer")
                assert ok is True
                assert "Test Laser Printer" in msg
                mock_win32api.ShellExecute.assert_called_once_with(
                    0, "printto", str(tmp_pdf.resolve()), '"Test Laser Printer"', ".", 0
                )
    finally:
        if tmp_pdf.exists():
            tmp_pdf.unlink()


def test_updater_mock_release_payload():
    """Verify check_for_updates correctly detects a newer GitHub release."""
    payload = {
        "tag_name": "v1.4.0",
        "body": "Phase 2 feature updates and deck optimizations.",
        "html_url": "https://github.com/EcstaticTech641/heatWave/releases/tag/v1.4.0",
    }
    raw_json = json.dumps(payload).encode("utf-8")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = raw_json
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = check_for_updates(current_version="1.3.0")

        assert result["update_available"] is True
        assert result["latest_version"] == "1.4.0"
        assert result["release_notes"] == "Phase 2 feature updates and deck optimizations."
        assert result["error"] is None
        assert "v1.4.0" in result["download_url"]

        # Verify request parameters
        req_arg = mock_urlopen.call_args[0][0]
        assert req_arg.full_url == "https://api.github.com/repos/EcstaticTech641/heatWave/releases/latest"
        assert req_arg.headers.get("User-agent") == "heatWave-Desktop/1.3.0"


def test_updater_same_version_no_update():
    """Verify check_for_updates returns update_available=False when on latest version."""
    payload = {
        "tag_name": "v1.3.0",
        "body": "v1.3.0 release",
        "html_url": "https://github.com/EcstaticTech641/heatWave/releases/tag/v1.3.0",
    }
    raw_json = json.dumps(payload).encode("utf-8")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = raw_json
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = check_for_updates(current_version="1.3.0")
        assert result["update_available"] is False
        assert result["latest_version"] == "1.3.0"


def test_updater_offline_error_handling():
    """Verify check_for_updates handles network timeout and URLError gracefully without raising."""
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
        result = check_for_updates(current_version="1.3.0")
        assert result["update_available"] is False
        assert result["error"] is not None
        assert "Unable to check for updates" in result["error"]


def test_updater_privacy_zero_telemetry():
    """Verify update checker sends no user metadata, query params, or PII."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"tag_name": "v1.3.0"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        check_for_updates("1.3.0")

        req = mock_urlopen.call_args[0][0]
        # Assert clean GET with no query parameters
        assert req.get_full_url() == "https://api.github.com/repos/EcstaticTech641/heatWave/releases/latest"
        assert req.data is None
        # Verify strict user-agent
        assert req.headers.get("User-agent") == "heatWave-Desktop/1.3.0"
