#!/usr/bin/env python
"""Build script to create heatWave.exe"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

# Change to project directory (where this script is)
os.chdir(Path(__file__).parent.absolute())

def get_project_version() -> str:
    """Extract version from pyproject.toml dynamically."""
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        import re
        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_path.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return "1.2.1"

version = get_project_version()
print(f"[*] Target version: v{version}")

# Clean previous builds
print("[*] Cleaning previous builds...")
for folder in ["build", "dist"]:
    if Path(folder).exists():
        shutil.rmtree(folder)
        print(f"    Removed {folder}/")

# Run PyInstaller
print("[*] Starting PyInstaller build...")
print("    Using spec file: heatWave.spec")

try:
    # Run with unbuffered output
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "heatWave.spec"],
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        timeout=600
    )
    
    exit_code = result.returncode
    print(f"\n[*] PyInstaller finished with exit code: {exit_code}")
    
    # Check for output
    if Path("dist").exists():
        dist_contents = list(Path("dist").rglob("*"))
        print(f"[+] Found {len(dist_contents)} items in dist/")
        
        exe_path = Path("dist/heatWave/heatWave.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024*1024)
            print(f"[+] SUCCESS: heatWave.exe created ({size_mb:.1f} MB)")
            
            # --- Task 1: Create Portable Zip Package ---
            zip_filename = f"heatWave_v{version}_portable"
            zip_output_path = Path("dist") / zip_filename
            print(f"[*] Packaging portable zip archive ({zip_filename}.zip)...")
            shutil.make_archive(
                str(zip_output_path),
                format="zip",
                root_dir="dist",
                base_dir="heatWave",
            )
            zip_file = Path("dist") / f"{zip_filename}.zip"
            if zip_file.exists():
                zip_size_mb = zip_file.stat().st_size / (1024 * 1024)
                print(f"[+] SUCCESS: Portable zip created: {zip_file} ({zip_size_mb:.1f} MB)")
            else:
                print(f"[-] ERROR: Failed to create {zip_file}")
        else:
            print("[-] ERROR: heatWave.exe not found in dist/")
            print("[*] Contents of dist/:")
            for item in dist_contents[:20]:
                print(f"    {item}")
    else:
        print("[-] ERROR: dist/ folder was not created")
        
except subprocess.TimeoutExpired:
    print("[-] ERROR: Build timed out after 600 seconds")
except Exception as e:
    print(f"[-] ERROR: {e}")
    import traceback
    traceback.print_exc()
