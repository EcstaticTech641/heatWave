#!/usr/bin/env powershell
<#
.SYNOPSIS
    Build heatWave.exe from source using PyInstaller
    
.DESCRIPTION
    One-command builder for heatWave Windows executable
    Handles cleanup, build, verification, and instructions
    
.EXAMPLE
    .\build.ps1
    
.NOTES
    Requires: Python 3.10+, PyInstaller, project dependencies
#>

param(
    [switch]$Clean = $false,
    [switch]$Fast = $false,
    [switch]$Onefile = $false
)

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "[STEP] $Text" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Text)
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Text)
    Write-Host "[ERROR] $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "[INFO] $Text" -ForegroundColor Cyan
}

# Check if we're in the right directory
if (-not (Test-Path "heatWave.spec")) {
    Write-Error-Custom "heatWave.spec not found. Please run this script from the project root."
    exit 1
}

Write-Header "heatWave .exe Builder"

# Step 1: Check prerequisites
Write-Step "Checking prerequisites..."

# Check Python
try {
    $python_version = python --version 2>&1
    Write-Success "Python found: $python_version"
} catch {
    Write-Error-Custom "Python not found. Please install Python 3.10+"
    exit 1
}

# Check PyInstaller
try {
    $pyinstaller_version = pyinstaller --version 2>&1
    Write-Success "PyInstaller found: $pyinstaller_version"
} catch {
    Write-Error-Custom "PyInstaller not found. Installing..."
    pip install pyinstaller
}

# Check virtual environment
if ($env:VIRTUAL_ENV) {
    Write-Success "Virtual environment activated: $env:VIRTUAL_ENV"
} else {
    Write-Info "No virtual environment detected. Attempting to activate .venv..."
    if (Test-Path ".venv\Scripts\Activate.ps1") {
        & .\.venv\Scripts\Activate.ps1
        Write-Success "Activated .venv"
    } else {
        Write-Info "No .venv found. Using system Python (not recommended for distribution)"
    }
}

# Step 2: Clean previous builds (optional)
if ($Clean -or (Test-Path "dist") -or (Test-Path "build")) {
    Write-Step "Cleaning previous builds..."
    Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "build" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "heatWave" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Success "Previous builds cleaned"
}

# Step 3: Build with PyInstaller
Write-Step "Building heatWave.exe with PyInstaller..."
Write-Info "This may take 3-5 minutes..."

$build_args = @("--clean", "heatWave.spec")

if ($Onefile) {
    Write-Info "Building as single .exe (slower startup)"
    $build_args += "--onefile"
}

if ($Fast) {
    Write-Info "Fast mode: skipping compression"
    # Already fast by default with folder structure
}

try {
    # Use python -m PyInstaller to ensure correct path
    & python -m PyInstaller @build_args 2>&1 | ForEach-Object {
        if ($_ -match "Warning|warning") {
            Write-Host "     WARNING: $_" -ForegroundColor Yellow
        } elseif ($_ -match "Error|error|failed") {
            Write-Host "     ERROR: $_" -ForegroundColor Red
        } elseif ($_ -match "completed|completed successfully") {
            Write-Host "     $_" -ForegroundColor Green
        } else {
            # Show progress percentage
            if ($_ -match "(\d+%)") {
                Write-Host "     $($_)" -ForegroundColor Gray
            }
        }
    }
    Write-Success "Build completed"
} catch {
    Write-Error-Custom "PyInstaller build failed: $_"
    exit 1
}

# Step 4: Verify output
Write-Step "Verifying output..."

$exe_path = "dist\heatWave\heatWave.exe"
if (Test-Path $exe_path) {
    $file_size = (Get-Item $exe_path).Length / 1MB
    Write-Success "heatWave.exe created: $([Math]::Round($file_size, 1)) MB"
    
    # List files in dist
    Write-Info "Distribution package contents:"
    Get-ChildItem -Path "dist\heatWave" -Recurse | 
        Where-Object { -not $_.PSIsContainer } | 
        ForEach-Object { 
            $size = $_.Length / 1MB
            $formatted_size = [Math]::Round($size, 1)
            Write-Host "      $($_.Name) ($formatted_size MB)" -ForegroundColor Gray
        }
} else {
    Write-Error-Custom "heatWave.exe not found! Build may have failed."
    exit 1
}

# Step 5: Instructions
Write-Header "Build Successful - Ready to Test!"

Write-Host "Your heatWave executable is ready:" -ForegroundColor Green
$exe_location = Resolve-Path 'dist\heatWave\heatWave.exe'
Write-Host "  [Location] $exe_location" -ForegroundColor Cyan
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Green
Write-Host ""
Write-Host "[1] TEST LOCALLY:" -ForegroundColor Yellow
Write-Host "   cd dist\heatWave" -ForegroundColor Gray
Write-Host "   .\heatWave.exe" -ForegroundColor Gray
Write-Host ""

Write-Host "[2] VERIFY IT WORKS:" -ForegroundColor Yellow
Write-Host "   - Browser should open automatically" -ForegroundColor Gray
Write-Host "   - Upload a PDF" -ForegroundColor Gray
Write-Host "   - Generate heat sheets" -ForegroundColor Gray
Write-Host "   - Download PDF" -ForegroundColor Gray
Write-Host ""

Write-Host "[3] DISTRIBUTE TO COACHES:" -ForegroundColor Yellow
Write-Host "   Option A: Zip the entire 'dist\heatWave' folder" -ForegroundColor Gray
Write-Host "   Option B: Share 'heatWave.exe' with all bundled files" -ForegroundColor Gray
Write-Host ""

Write-Host "[4] COACH INSTRUCTIONS:" -ForegroundColor Yellow
Write-Host "   - Download heatWave.exe" -ForegroundColor Gray
Write-Host "   - Double-click it" -ForegroundColor Gray
Write-Host "   - Browser opens, app is ready to use" -ForegroundColor Gray
Write-Host ""

Write-Host "For detailed build guide, see: BUILD_GUIDE.md" -ForegroundColor Cyan
Write-Host ""

# Optional: Offer to test
$test_response = Read-Host "Would you like to test the .exe now? (y/n)"
if ($test_response -eq 'y' -or $test_response -eq 'Y') {
    Write-Step "Starting heatWave.exe..."
    Write-Info "Application is starting. Browser should open in 5-10 seconds..."
    & ".\dist\heatWave\heatWave.exe"
}

Write-Host ""
Write-Header "Build Complete"
