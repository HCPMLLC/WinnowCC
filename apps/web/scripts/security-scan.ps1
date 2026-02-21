# Security scan script for JavaScript dependencies
Write-Host "=== Running npm audit ===" -ForegroundColor Cyan
npm audit --production

Write-Host ""
Write-Host "=== Scan complete ===" -ForegroundColor Green
