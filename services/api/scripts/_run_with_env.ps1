# Helper: load .env and run a Python script
param([string]$Script, [string[]]$Args)

$apiRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envFile = Join-Path $apiRoot ".env"
Write-Host "Loading env from: $envFile"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$' -and $_ -notmatch '^\s*#') {
            $key = $Matches[1]
            $val = $Matches[2].Trim("'`"")
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
    Write-Host "DB_URL = $([Environment]::GetEnvironmentVariable('DB_URL', 'Process'))"
} else {
    Write-Host "WARNING: .env file not found at $envFile"
}

$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
& $python $Script @Args
exit $LASTEXITCODE
