param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$EnvFile = Join-Path $Backend ".env"
$EnvExample = Join-Path $Backend ".env.example"

function Require-Command($Name, $Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found. $Hint"
    }
}

Require-Command "python" "Install Python 3.10+ and add it to PATH."
Require-Command "node" "Install Node.js 18+ and add it to PATH."
Require-Command "npm.cmd" "Install Node.js/npm and add it to PATH."
Require-Command "java" "Install JDK 17 and add it to PATH."
Require-Command "mvn.cmd" "Install Maven 3.9+ and add it to PATH."

if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "Created backend\.env from backend\.env.example. Fill AI_PLANNER_API_KEY and model before creating tasks." -ForegroundColor Yellow
}

if (-not $SkipInstall) {
    Push-Location $Backend
    python -m pip install -r requirements.txt
    python -m playwright install chromium
    Pop-Location

    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Push-Location $Frontend
        npm.cmd install
        Pop-Location
    }
}

$BackendLog = Join-Path $Root "backend-server-current.log"
$FrontendLog = Join-Path $Root "frontend-server.log"

$BackendCommand = "cd `"$Backend`"; python -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort 2>&1 | Tee-Object -FilePath `"$BackendLog`""
$FrontendCommand = "cd `"$Frontend`"; npm.cmd run dev -- --host 127.0.0.1 --port $FrontendPort 2>&1 | Tee-Object -FilePath `"$FrontendLog`""

Start-Process powershell.exe -WorkingDirectory $Backend -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $BackendCommand
)

Start-Process powershell.exe -WorkingDirectory $Frontend -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", $FrontendCommand
)

$Url = "http://127.0.0.1:$FrontendPort"
Write-Host "Backend:  http://127.0.0.1:$BackendPort" -ForegroundColor Green
Write-Host "Frontend: $Url" -ForegroundColor Green
Write-Host "Logs:     backend-server-current.log, frontend-server.log"

if (-not $NoBrowser) {
    Start-Process $Url
}
