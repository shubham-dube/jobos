# Start JobOS (server + agents, dashboard, runner) in separate windows.
#   powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
docker compose -f "$root\docker-compose.yml" up -d postgres | Out-Null
# load .env into this process so the dashboard gets JOBOS_API_URL / TOKEN / PASSWORD
Get-Content "$root\.env" | Where-Object { $_ -match "^[A-Z_]+=" } | ForEach-Object {
  $k, $v = $_.Split("=", 2); [System.Environment]::SetEnvironmentVariable($k, ($v -replace "\s+#.*$", ""))
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; uv run jobos serve --role all"
Start-Sleep -Seconds 8
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\apps\web'; pnpm start"
$cfg = Join-Path $env:LOCALAPPDATA "JobOS\runner.json"
if (Test-Path $cfg) {
  Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; uv run jobos-runner run"
} else {
  Write-Host "Runner not configured yet: open http://localhost:3000/settings -> Create runner token, then run"
  Write-Host "  uv run jobos-runner setup --api http://localhost:8000 --token <token>"
  Write-Host "  uv run jobos-runner login     (sign in to Google first, then LinkedIn/Naukri)"
}
Start-Process "http://localhost:3000"
