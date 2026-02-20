# stop-dev.ps1
# Kill all Winnow dev processes listening on known ports (3000-3002, 8000).
# Safe to run when nothing is running — errors are silenced.

$ports = @(3000, 3001, 3002, 8000)
$killed = 0

foreach ($port in $ports) {
  try {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
      $pid = $conn.OwningProcess
      $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
      if ($proc) {
        Write-Host "Killing PID $pid ($($proc.ProcessName)) on port $port" -ForegroundColor Yellow
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        $killed++
      }
    }
  } catch {
    # Port not in use — nothing to do
  }
}

if ($killed -eq 0) {
  Write-Host "No dev processes found on ports $($ports -join ', ')." -ForegroundColor Green
} else {
  Write-Host "Stopped $killed process(es)." -ForegroundColor Green
}
