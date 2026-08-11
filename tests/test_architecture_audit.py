"""
Architecture Audit Test Suite.

Automated verification to ensure business logic and parser packages
(src/parser, src/seeding, src/core, src/models) remain completely decoupled
from UI frameworks (streamlit, pywebview) and platform-specific modules (win32print, win32api).
"""
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CORE_PACKAGES = [
    PROJECT_ROOT / "src" / "parser",
    PROJECT_ROOT / "src" / "seeding",
    PROJECT_ROOT / "src" / "core",
    PROJECT_ROOT / "src" / "models",
]

FORBIDDEN_IMPORTS = {"streamlit", "win32print", "win32api", "pywebview"}


def test_no_forbidden_ui_or_platform_imports_in_core():
    """Verify src/parser, src/seeding, src/core, src/models contain 0 forbidden imports."""
    py_files = []
    for pkg in CORE_PACKAGES:
        if pkg.exists():
            py_files.extend(list(pkg.rglob("*.py")))

    assert len(py_files) > 0, "No core Python source files found"

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_base = alias.name.split(".")[0]
                    assert (
                        mod_base not in FORBIDDEN_IMPORTS
                    ), f"Forbidden import '{alias.name}' detected in {py_file.relative_to(PROJECT_ROOT)}"

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_base = node.module.split(".")[0]
                    assert (
                        mod_base not in FORBIDDEN_IMPORTS
                    ), f"Forbidden import '{node.module}' detected in {py_file.relative_to(PROJECT_ROOT)}"
