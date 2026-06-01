#!/usr/bin/env python
"""Build script to create heatWave.exe"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

# Change to project directory
os.chdir(r"r:\aaron\programs\heatWave")

# Clean previous builds
print("[*] Cleaning previous builds...")
for folder in ["build", "dist"]:
    if Path(folder).exists():
        shutil.rmtree(folder)
        print(f"    Removed {folder}/")

# Run PyInstaller
print("[*] Starting PyInstaller build...")
print("    Using spec file: heatWave_simple.spec")

try:
    # Run with unbuffered output
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "heatWave_simple.spec"],
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
            print(f"[✓] SUCCESS: heatWave.exe created ({size_mb:.1f} MB)")
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
