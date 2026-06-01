# heatWave .exe Building Guide

## Overview
This guide walks you through packaging heatWave as a standalone Windows .exe that coaches can download and run with zero setup.

**Result:** `heatWave.exe` (150-250 MB) that opens in the browser when clicked

---

## Prerequisites

### 1. Python 3.10+ Installed
Check your Python version:
```bash
python --version
```

### 2. Virtual Environment with Dependencies
Make sure your .venv is activated and all requirements installed:
```bash
# On Windows
.venv\Scripts\activate

# Check dependencies
pip list | grep streamlit
```

### 3. PyInstaller
Install PyInstaller:
```bash
pip install pyinstaller
```

---

## Build Steps (10 minutes)

### Step 1: Clean Previous Builds
```bash
# Remove old build artifacts
rmdir /s /q build dist heatWave
del *.spec 2>nul
```

### Step 2: Build with heatWave.spec
```bash
# Make sure you're in the project root directory
cd r:\aaron\programs\heatWave

# Activate your virtual environment
.venv\Scripts\activate

# Run PyInstaller
pyinstaller --clean heatWave.spec
```

**What's happening:**
- PyInstaller reads `heatWave.spec` configuration
- Analyzes `run_streamlit.py` and all dependencies
- Bundles everything into `dist/heatWave/`
- Creates `dist/heatWave.exe`

**Build time:** 3-5 minutes depending on your system

### Step 3: Check Output
```bash
# Verify the executable exists
ls -la dist/heatWave/heatWave.exe

# Or on Windows PowerShell:
Get-Item dist\heatWave\heatWave.exe
```

Expected output: File around 150-250 MB

---

## Test Locally

### Test 1: Run from Command Prompt
```bash
cd dist\heatWave
heatWave.exe
```

**Expected behavior:**
1. Console window opens briefly
2. "🏊 Starting heatWave..." message
3. Browser opens to `http://localhost:8501`
4. Streamlit UI loads (may take 10-15 seconds first time)

### Test 2: Double-Click Test
1. Open Windows File Explorer
2. Navigate to `dist\heatWave\`
3. Double-click `heatWave.exe`
4. Verify browser opens and app loads

### Test 3: Full Workflow Test
1. Upload a PDF
2. Parse it
3. Generate heat sheets
4. Download the PDFs
5. Verify the application works end-to-end

### Test 4: Clean Machine Test (Optional but Recommended)
To truly verify zero dependencies:
1. Copy `dist\heatWave\` folder to a USB drive
2. Plug USB into a **clean Windows machine with NO Python installed**
3. Run `heatWave.exe` - should work perfectly

---

## Distribution

### Package for Download

#### Option 1: Standalone Folder (Easy)
```bash
# Zip the entire dist/heatWave folder
# Users download and extract: heatWave.zip (200 MB)
# They run: heatWave.exe
```

**Pros:** 
- Simple - one folder, one .exe
- All files together
- Users just extract and run

**Cons:**
- Larger download (200 MB)

#### Option 2: Installer (Professional)
Use NSIS to create an installer:
```bash
# Create heatWave-installer.exe (~80 MB)
# Users run installer → Desktop shortcut created
# Much cleaner distribution
```

**Create a simple NSIS script:**
```nsis
; heatWave-installer.nsi
!include "MUI2.nsh"

Name "heatWave"
OutFile "heatWave-installer.exe"
InstallDir "$PROGRAMFILES\heatWave"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "dist\heatWave\*"
  CreateShortCut "$SMPROGRAMS\heatWave.lnk" "$INSTDIR\heatWave.exe"
  CreateShortCut "$DESKTOP\heatWave.lnk" "$INSTDIR\heatWave.exe"
SectionEnd
```

Build installer:
```bash
# Download NSIS from https://nsis.sourceforge.io/
# Then:
makensis heatWave-installer.nsi
# Creates: heatWave-installer.exe
```

### Upload & Share

**Option A: GitHub Releases**
```bash
# Create a GitHub release
# Upload heatWave.exe (or heatWave.zip)
# Coaches download from: github.com/your-repo/releases
```

**Option B: Google Drive / Dropbox**
- Share the .zip or .exe directly
- Simple for small distributions

**Option C: Website**
- Host on your coaching website
- One-click download button

---

## Troubleshooting

### Issue: "heatWave.exe is not a valid Win32 application"
**Cause:** PyInstaller failed or corrupted build
**Fix:**
```bash
# Rebuild from scratch
rmdir /s /q build dist
pyinstaller --clean heatWave.spec
```

### Issue: Port 8501 already in use
**Cause:** Another instance of heatWave or Streamlit is running
**Fix:**
```bash
# Find and kill the process
netstat -ano | findstr :8501
taskkill /PID <PID> /F
```

### Issue: "ModuleNotFoundError: No module named X"
**Cause:** Hidden import missing in heatWave.spec
**Fix:**
```bash
# Add the missing module to hiddenimports in heatWave.spec
# Rebuild:
pyinstaller --clean heatWave.spec
```

### Issue: .exe won't start, no error message
**Cause:** Probably missing a required system DLL or library
**Fix:**
```bash
# Run with debug mode to see errors
# Edit heatWave.spec: change console=False to console=True
# Rebuild and run - you'll see error messages
pyinstaller --clean heatWave.spec
dist\heatWave\heatWave.exe
```

### Issue: First launch is very slow (30+ seconds)
**Cause:** Normal - first run unpacks and initializes Streamlit cache
**Fix:** Wait longer (this is expected behavior)

### Issue: File size is too large (>300 MB)
**Cause:** Too many dependencies or unnecessary libraries included
**Fix:**
```bash
# Try excluding more unused libraries in heatWave.spec
# Or use UPX compression (already enabled):
pyinstaller --clean --onefile heatWave.spec  # Single file instead of folder
```

---

## Optimization Tips

### 1. Reduce File Size
- Use `--onefile` flag to create single .exe instead of folder (note: slower startup)
- Remove unused libraries from `excludes` list in heatWave.spec
- Enable UPX compression (already on in spec)

### 2. Faster Startup
- Avoid `--onefile` (use folder structure, which is default)
- Pre-compile bytecode
- Cache compiled modules

### 3. Icon & Branding
Create an icon:
```bash
# Place icon.ico in project root
# PyInstaller will automatically include it
# Or edit heatWave.spec and set icon='path/to/icon.ico'
```

### 4. Version Info
Add version to your app:
```bash
# Windows will show version when you right-click heatWave.exe → Properties
# Edit heatWave.spec to add version_file='file_version_info.txt'
```

---

## Advanced: Create a Silent Installer

For mass distribution to coaches:

```bash
# Create a completely silent installer with no console window
# Edit heatWave.spec:
#   console=False              (already set)
#   icon='icon.ico'            (add your logo)

# Build as single file for easier distribution:
pyinstaller heatWave.spec --onefile

# Creates: dist/heatWave.exe (slower startup but cleaner)
```

---

## Verification Checklist

Before distributing to coaches:

- [ ] Built with `pyinstaller --clean heatWave.spec`
- [ ] Tested locally by double-clicking .exe
- [ ] Tested full workflow (upload → parse → generate → download)
- [ ] Downloaded PDFs look correct and work in Adobe/browsers
- [ ] File size is reasonable (150-250 MB)
- [ ] Tested on a clean Windows machine with no Python
- [ ] Browser opens automatically when .exe starts
- [ ] No console window visible (console=False working)
- [ ] Created appropriate distribution package (.zip or installer)

---

## Deployment to Coaches

### Instructions to Give Coaches:

1. **Download** `heatWave.exe` (or `heatWave.zip`)
2. **Extract** (if zip) or move `.exe` to desired location (e.g., Desktop)
3. **Double-click** `heatWave.exe` to launch
4. **Wait 5-10 seconds** for browser to open
5. **Use** the web interface exactly like the online version
6. **Close** the app by closing the browser or hitting Ctrl+C in any console

**Important Notes:**
- ✅ No installation required
- ✅ No Python needed
- ✅ Works offline (for local PDF processing)
- ✅ Safe and anonymous (zero data stored)

---

## Next Steps

1. Follow **Build Steps** above to create the .exe
2. Run **Test Locally** to verify everything works
3. Choose a **Distribution** method (folder, .zip, or installer)
4. Share with coaches!

---

## Support & Feedback

If you encounter issues:
1. Check **Troubleshooting** section above
2. Check the `build/` and `dist/` logs
3. Rebuild with `console=True` to see error messages
4. Create an issue with detailed error output

Good luck! 🏊
