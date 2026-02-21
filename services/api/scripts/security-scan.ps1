# Security scan script for Python dependencies
Write-Host "=== Running pip-audit (Python dependency vulnerability scan) ===" -ForegroundColor Cyan
pip-audit --strict --desc

Write-Host ""
Write-Host "=== Running Ruff security checks ===" -ForegroundColor Cyan
python -m ruff check . --select S  # S = Bandit security rules

Write-Host ""
Write-Host "=== Scan complete ===" -ForegroundColor Green
