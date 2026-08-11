"""
Privacy and Security Audit Test Suite.

Automated verification to ensure heatWave remains 100% offline,
collects zero telemetry/analytics, stores no PII on disk, and contains
no network-bound code paths in runtime source modules.
"""
import ast
import os
from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_TOML = PROJECT_ROOT / ".streamlit" / "config.toml"
RUN_DESKTOP = PROJECT_ROOT / "run_desktop.py"

PROHIBITED_MODULES = {
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "sentry_sdk",
    "posthog",
    "mixpanel",
    "datadog",
    "telemetry",
    "analytics",
    "segment",
}


def test_no_external_network_imports():
    """Verify no prohibited network, tracking, or telemetry libraries are imported in src/."""
    python_files = list(SRC_DIR.rglob("*.py"))
    assert len(python_files) > 0, "No Python source files found under src/"

    for py_file in python_files:
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_base = alias.name.split(".")[0]
                    assert (
                        module_base not in PROHIBITED_MODULES
                    ), f"Prohibited module '{alias.name}' imported in {py_file.relative_to(PROJECT_ROOT)}"

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_base = node.module.split(".")[0]
                    assert (
                        module_base not in PROHIBITED_MODULES
                    ), f"Prohibited module '{node.module}' imported in {py_file.relative_to(PROJECT_ROOT)}"


def test_streamlit_telemetry_disabled():
    """Verify Streamlit usage stats collection is explicitly disabled in config.toml and run_desktop.py."""
    # 1. Check .streamlit/config.toml
    assert CONFIG_TOML.exists(), f"Missing configuration file at {CONFIG_TOML}"
    with open(CONFIG_TOML, "rb") as f:
        config_data = tomllib.load(f)

    assert "browser" in config_data, "[browser] section missing in config.toml"
    assert (
        config_data["browser"].get("gatherUsageStats") is False
    ), "gatherUsageStats must be explicitly set to false in config.toml"

    # 2. Check run_desktop.py environment setting
    assert RUN_DESKTOP.exists(), f"Missing launcher script at {RUN_DESKTOP}"
    desktop_code = RUN_DESKTOP.read_text(encoding="utf-8")
    assert (
        'os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"' in desktop_code
    ), "run_desktop.py must explicitly set STREAMLIT_BROWSER_GATHER_USAGE_STATS to false"


def test_no_disk_pii_logging():
    """Verify loggers in src/ do not log athlete names, seed times, or swimmer PII to disk."""
    pii_keywords = {"swimmer.name", "athlete_name", "seed_time", "entry.swimmer"}
    
    python_files = list(SRC_DIR.rglob("*.py"))
    for py_file in python_files:
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Inspect logger calls (e.g. logger.info, logger.error, logger.warning)
                if isinstance(node.func, ast.Attribute) and node.func.attr in {
                    "debug",
                    "info",
                    "warning",
                    "error",
                    "critical",
                    "log",
                }:
                    # Convert arguments AST back to string representation
                    for arg in node.args:
                        arg_code = ast.unparse(arg)
                        for keyword in pii_keywords:
                            assert (
                                keyword not in arg_code
                            ), f"Potential PII field '{keyword}' detected in log statement in {py_file.relative_to(PROJECT_ROOT)}"
