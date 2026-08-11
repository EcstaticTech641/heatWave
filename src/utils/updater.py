"""
Privacy-Safe Manual Update Checker.
Queries GitHub Releases API strictly upon user request (100% user-initiated).
Collects and transmits zero telemetry, device metrics, or PII.
"""
import json
import logging
import re
import socket
import urllib.error
import urllib.request
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

GITHUB_RELEASES_API = "https://api.github.com/repos/EcstaticTech641/heatWave/releases/latest"
DEFAULT_TIMEOUT_SECONDS = 5


def parse_version_tuple(version_str: str) -> Tuple[int, ...]:
    """Parse a semantic version string into a clean integer tuple for comparison."""
    if not isinstance(version_str, str):
        return (0, 0, 0)
    cleaned = version_str.strip().lstrip("v")
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", cleaned)
    if not match:
        return (0, 0, 0)
    parts = [int(g) if g is not None else 0 for g in match.groups()]
    return tuple(parts)


def check_for_updates(current_version: str = "1.3.2") -> Dict[str, Any]:
    """
    Manually check GitHub Releases API for newer heatWave releases.

    This function is 100% user-initiated and transmits zero telemetry or device IDs.

    Args:
        current_version: Current version of the heatWave application (e.g. "1.3.2").

    Returns:
        Dict containing:
            - update_available (bool): True if a newer version is available.
            - latest_version (str): Latest release tag string (e.g. "1.3.0").
            - release_notes (str): Release description notes from GitHub.
            - download_url (str): Link to GitHub releases download page.
            - error (str | None): Human-readable error message if check failed.
    """
    req = urllib.request.Request(
        GITHUB_RELEASES_API,
        headers={
            "User-Agent": f"heatWave-Desktop/{current_version}",
            "Accept": "application/vnd.github.v3+json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return {
                    "update_available": False,
                    "latest_version": current_version,
                    "release_notes": "",
                    "download_url": "https://github.com/EcstaticTech641/heatWave/releases",
                    "error": f"GitHub API returned HTTP status {response.status}",
                }

            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)

            raw_tag = data.get("tag_name", "")
            latest_version = raw_tag.lstrip("v").strip() if raw_tag else current_version
            release_notes = data.get("body", "No release notes available.")
            html_url = data.get("html_url", "https://github.com/EcstaticTech641/heatWave/releases")

            current_tuple = parse_version_tuple(current_version)
            latest_tuple = parse_version_tuple(latest_version)

            update_available = latest_tuple > current_tuple

            return {
                "update_available": update_available,
                "latest_version": latest_version,
                "release_notes": release_notes,
                "download_url": html_url,
                "error": None,
            }

    except urllib.error.HTTPError as e:
        logger.warning(f"GitHub release check HTTP error: {e.code}")
        return {
            "update_available": False,
            "latest_version": current_version,
            "release_notes": "",
            "download_url": "https://github.com/EcstaticTech641/heatWave/releases",
            "error": f"HTTP {e.code}: Unable to fetch release info.",
        }
    except (urllib.error.URLError, socket.timeout) as e:
        logger.info(f"Offline or timeout during release check: {e}")
        return {
            "update_available": False,
            "latest_version": current_version,
            "release_notes": "",
            "download_url": "https://github.com/EcstaticTech641/heatWave/releases",
            "error": "Network timeout or offline. Unable to check for updates.",
        }
    except Exception as e:
        logger.error(f"Unexpected error during update check: {e}")
        return {
            "update_available": False,
            "latest_version": current_version,
            "release_notes": "",
            "download_url": "https://github.com/EcstaticTech641/heatWave/releases",
            "error": f"Update check failed: {str(e)}",
        }
