# start-dev.ps1
# One-command dev startup for ResumeMatch (Windows)

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

Write-Host "== ResumeMatch dev startup ==" -ForegroundColor Cyan
Write-Host "Root:  $root"
Write-Host "Infra: $infra"
Write-Host "API:   $api"
Write-Host "Web:   $web"
Write-Host ""

# --- Start infra (Postgres + Redis) ---
Write-Host "[1/4] Starting Docker containers (Postgres + Redis)..." -ForegroundColor Yellow
Push-Location $infra
docker compose up -d | Out-Null
Pop-Location

# --- Start API (uvicorn) ---
Write-Host "[2/4] Starting API (uvicorn)..." -ForegroundColor Yellow
Start-NewPSWindow `
  -title "ResumeMatch API" `
  -workingDir $api `
  -command ".\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload"

# --- Start Worker (RQ) ---
Write-Host "[3/4] Starting Worker (RQ)..." -ForegroundColor Yellow
Start-NewPSWindow `
  -title "ResumeMatch Worker" `
  -workingDir $api `
  -command ".\.venv\Scripts\Activate.ps1; python -m app.worker"

# --- Start Web (Next.js) ---
Write-Host "[4/4] Starting Web (Next.js)..." -ForegroundColor Yellow
Start-NewPSWindow `
  -title "ResumeMatch Web" `
  -workingDir $web `
  -command "npm run dev"

Write-Host ""
Write-Host "Done. Open the web app URL shown in the 'ResumeMatch Web' window (usually http://localhost:3000 or :3001)." -ForegroundColor Green
Write-Host "API should be at http://127.0.0.1:8000 (see the 'ResumeMatch API' window)." -ForegroundColor Green
