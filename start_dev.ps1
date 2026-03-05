# Exegol V2 - Development Startup Script
# Double-click or run: .\start_dev.ps1
# Starts backend (FastAPI) and frontend (Next.js), then opens the dashboard in your browser.

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "Exegol V2 - Starting development environment..." -ForegroundColor Cyan

# 1. Check or create backend venv
$backendPath = Join-Path $ProjectRoot "backend"
$venvPath = Join-Path $backendPath "venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Yellow
    Push-Location $backendPath
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv venv
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        python3 -m venv venv
    } else {
        py -m venv venv
    }
    & (Join-Path $venvPath "Scripts\Activate.ps1")
    pip install -r requirements.txt
    Pop-Location
    Write-Host "Venv created and dependencies installed." -ForegroundColor Green
} else {
    Write-Host "Backend venv found." -ForegroundColor Green
}

# 2. Start FastAPI in a new window
$backendCmd = @"
cd '$backendPath'
& .\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# 3. Start frontend in a new window
$frontendPath = Join-Path $ProjectRoot "frontend"
$frontendCmd = "cd '$frontendPath'; npm run dev; pause"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

# 4. Wait for services to start
Write-Host "Waiting for backend and frontend to start (10s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 5. Open browser to dashboard
Write-Host "Opening dashboard at http://localhost:3000" -ForegroundColor Cyan
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Exegol Control Dashboard launched." -ForegroundColor Green
Write-Host "- Backend: http://127.0.0.1:8000 (see backend window)" -ForegroundColor Gray
Write-Host "- Frontend: http://localhost:3000 (see frontend window)" -ForegroundColor Gray
Write-Host "Close the backend and frontend windows to stop." -ForegroundColor Gray
