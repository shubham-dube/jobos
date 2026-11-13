# JobOS one-time setup for Windows 11 (PowerShell). Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
$ErrorActionPreference = "Stop"
function Need($cmd, $wingetId) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "Installing $wingetId ..."; winget install --id=$wingetId -e --accept-source-agreements --accept-package-agreements
  }
}
Need uv "astral-sh.uv"
Need node "OpenJS.NodeJS.LTS"
Need docker "Docker.DockerDesktop"
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { npm install -g pnpm }
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

if (-not (Test-Path ".env")) {
  Copy-Item .env.example .env
  $rand = -join ((48..57) + (97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
  (Get-Content .env) -replace "change-me-long-random-string", $rand.Substring(0,32) `
                     -replace "change-me-32-plus-random-characters-here", $rand `
                     -replace "JOBOS_WEB_PASSWORD=change-me", "JOBOS_WEB_PASSWORD=$($rand.Substring(32,12))" | Set-Content .env
  Write-Host "Created .env - add your JOBOS_OPENROUTER_API_KEY and Resend settings now (notepad .env)."
}
uv sync --all-packages
Push-Location apps/web; pnpm install; pnpm build; Pop-Location
docker compose up -d postgres
Start-Sleep -Seconds 5
uv run jobos migrate
Write-Host "Setup done. Next: scripts\windows\start.ps1, then 'uv run jobos-runner login' once."
