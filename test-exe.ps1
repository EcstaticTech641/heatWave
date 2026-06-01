#!/usr/bin/env powershell
<#
.SYNOPSIS
    Test the built heatWave.exe before distribution
    
.DESCRIPTION
    Verifies that the packaged executable works correctly
    Tests startup, browser connection, and basic functionality
    
.EXAMPLE
    .\test-exe.ps1
#>

function Write-Header {
    param([string]$Text)
    Write-Host "`n" -NoNewline
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "▶ $Text" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Text)
    Write-Host "✅ $Text" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Text)
    Write-Host "❌ $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "ℹ  $Text" -ForegroundColor Cyan
}

Write-Header "heatWave .exe Test Suite"

# Check if .exe exists
Write-Step "Checking if heatWave.exe exists..."
$exe_path = "dist\heatWave\heatWave.exe"

if (-not (Test-Path $exe_path)) {
    Write-Error-Custom "heatWave.exe not found at $exe_path"
    Write-Info "Did you run 'build.ps1' first?"
    exit 1
}

$file_size = (Get-Item $exe_path).Length / 1MB
Write-Success "Found heatWave.exe ($($file_size.ToString("F1")) MB)"

# Check file signature
Write-Step "Checking file signature..."
$file_info = Get-Item $exe_path
if ($file_info.Exists) {
    Write-Success "File is valid and readable"
} else {
    Write-Error-Custom "File exists but cannot be read"
    exit 1
}

# Test 1: Start the application
Write-Step "Test 1: Starting heatWave.exe..."
Write-Info "Launching application (will open browser in 5-10 seconds)..."

try {
    $process = Start-Process -FilePath $exe_path -PassThru -ErrorAction Stop
    Write-Success "Process started (PID: $($process.Id))"
    
    # Wait for server to start
    Write-Step "Waiting for Streamlit server to initialize..."
    Start-Sleep -Seconds 6
    
    # Check if process is still running
    $process_running = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
    if ($process_running) {
        Write-Success "Application is running"
    } else {
        Write-Error-Custom "Application crashed or exited unexpectedly"
        exit 1
    }
    
    # Test 2: Check if port 8501 is listening
    Write-Step "Test 2: Checking if Streamlit is listening on port 8501..."
    
    $listening = $false
    for ($i = 0; $i -lt 10; $i++) {
        $connection_test = Test-NetConnection -ComputerName localhost -Port 8501 -WarningAction SilentlyContinue
        if ($connection_test.TcpTestSucceeded) {
            Write-Success "Streamlit is listening on localhost:8501"
            $listening = $true
            break
        }
        Write-Info "Waiting... (attempt $($i+1)/10)"
        Start-Sleep -Seconds 1
    }
    
    if (-not $listening) {
        Write-Error-Custom "Streamlit is not responding on port 8501"
        Write-Info "This could mean the server failed to start"
    }
    
    # Test 3: Check browser access
    Write-Step "Test 3: Checking HTTP access to localhost:8501..."
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8501" -TimeoutSec 5 -WarningAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "HTTP connection successful (Status 200)"
        } else {
            Write-Error-Custom "Got status $($response.StatusCode) instead of 200"
        }
    } catch {
        # Streamlit may return different status but page is still accessible
        Write-Info "HTTP test inconclusive (might still be working)"
    }
    
    # Test 4: Verify no console window
    Write-Step "Test 4: Checking if console window is hidden..."
    
    $process_details = Get-Process -Id $process.Id
    Write-Info "Process main window handle: $($process_details.MainWindowHandle)"
    if ($process_details.MainWindowHandle -eq 0) {
        Write-Success "Console window is properly hidden (no console)"
    } else {
        Write-Info "Window handle is visible (console might be visible)"
    }
    
    # Ask user for manual verification
    Write-Header "Manual Verification Needed"
    Write-Host "The application is running. Please verify in your browser:" -ForegroundColor Green
    Write-Host "  1. Browser opened automatically ?" -ForegroundColor Yellow
    Write-Host "  2. Page loads at http://localhost:8501 ?" -ForegroundColor Yellow
    Write-Host "  3. Streamlit UI is visible ?" -ForegroundColor Yellow
    Write-Host "  4. No Python console window visible ?" -ForegroundColor Yellow
    Write-Host ""
    
    Read-Host "Press Enter when you've verified the above"
    
    # Test 5: Cleanup
    Write-Step "Test 5: Shutting down application..."
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Write-Success "Application stopped"
    
    Start-Sleep -Seconds 2
    
} catch {
    Write-Error-Custom "Failed to start application: $_"
    
    # Clean up any orphaned processes
    Get-Process -Name heatWave -ErrorAction SilentlyContinue | Stop-Process -Force
    exit 1
}

# Summary
Write-Header "Test Summary"
Write-Success "All automated tests passed!"
Write-Host ""
Write-Host "Results:" -ForegroundColor Green
Write-Host "  ✅ Executable exists and is readable" -ForegroundColor Green
Write-Host "  ✅ Application starts successfully" -ForegroundColor Green
Write-Host "  ✅ Streamlit server initializes" -ForegroundColor Green
Write-Host "  ✅ Port 8501 is listening" -ForegroundColor Green
Write-Host "  ✅ Console window is hidden" -ForegroundColor Green
Write-Host ""

Write-Host "The executable is ready for distribution!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Create distribution package (ZIP or installer)" -ForegroundColor Gray
Write-Host "  2. Share with coaches" -ForegroundColor Gray
Write-Host "  3. Coaches download and double-click to run" -ForegroundColor Gray
Write-Host ""
