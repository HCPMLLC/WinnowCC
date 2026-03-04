# start-dev.ps1
# One-command dev startup for Winnow (Windows)

$ErrorActionPreference = "Stop"

# --- Helpers ---
function Ensure-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $name"
  }
}

function Start-NewPSWindow($title, $workingDir, $command) {
  # Opens a new PowerShell window and runs the command, keeping it open.
  $args = @(
    "-NoExit",
    "-Command",
    "Set-Location `"$workingDir`"; `$Host.UI.RawUI.WindowTitle = `"$title`"; $command"
  )
  Start-Process -FilePath "powershell.exe" -ArgumentList $args | Out-Null
}

# --- Preconditions ---
Ensure-Command "docker"
Ensure-Command "npm"

$root = (Resolve-Path ".").Path
$infra = Join-Path $root "infra"
$api = Join-Path $root "services\api"
$web = Join-Path $root "apps\web"

Write-Host "== Winnow dev startup ==" -ForegroundColor Cyan
Write-Host "Root:  $root"
Write-Host "Infra: $infra"
Write-Host "API:   $api"
Write-Host "Web:   $web"
Write-Host ""

# --- Kill stale processes ---
Write-Host "[0/5] Stopping stale dev processes..." -ForegroundColor Yellow
& (Join-Path $root "stop-dev.ps1")
Write-Host ""

# --- Start infra (Postgres + Redis) ---
Write-Host "[1/5] Starting Docker containers (Postgres + Redis)..." -ForegroundColor Yellow
Push-Location $infra
docker compose up -d | Out-Null
Pop-Location

# --- Start API (uvicorn) ---
Write-Host "[2/5] Starting API (uvicorn)..." -ForegroundColor Yellow
Start-NewPSWindow `
  -title "Winnow API" `
  -workingDir $api `
  -command ".\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload"

# --- Start Worker (RQ) ---
Write-Host "[3/5] Starting Worker (RQ)..." -ForegroundColor Yellow
Start-NewPSWindow `
  -title "Winnow Worker" `
  -workingDir $api `
  -command ".\.venv\Scripts\Activate.ps1; python -m app.worker"

# --- Start Scheduler (RQ Scheduler) ---
Write-Host "[4/5] Starting Scheduler (RQ Scheduler)..." -ForegroundColor Yellow
Start-NewPSWindow `
  -title "Winnow Scheduler" `
  -workingDir $api `
  -command ".\.venv\Scripts\Activate.ps1; python -m app.scheduler"

# --- Start Web (Next.js) ---
Write-Host "[5/5] Starting Web (Next.js)..." -ForegroundColor Yellow
Start-NewPSWindow `
  -title "Winnow Web" `
  -workingDir $web `
  -command "npm run dev"

Write-Host ""
Write-Host "Done. Web: http://localhost:3000 | API: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Stale processes are auto-killed - ports should always be correct." -ForegroundColor Green
