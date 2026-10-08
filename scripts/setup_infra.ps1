#requires -Version 5.1
<#
.SYNOPSIS
  One-command setup for the Airport Investment Intelligence Agent.

.DESCRIPTION
  Brings a fresh machine from "git clone" to a running demo:
    1. Verifies (or starts) the Docker engine.
    2. Starts the demo stack: backend :8000 + frontend :5173 + public
       Dify tool tunnel + local Whisper STT :8100 (-SkipVoice leaves STT out).
    3. Waits for the tunnel to answer /api/health on its public URL and
       syncs dify/openapi.yaml to that URL.
    4. Runs scripts/verify_infra.ps1 and prints the full service summary
       (every URL, what to re-sync in Dify, and the expected model setup).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\setup_infra.ps1
  powershell -ExecutionPolicy Bypass -File scripts\setup_infra.ps1 -SkipVoice
#>
param(
    [switch]$SkipVoice
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "tunnel.ps1")

# ---------------------------------------------------------------- .env file ---
# Docker Compose automatically reads `.env` from the repo root, but Docker can
# never CREATE it. Bootstrap it from `.env.example` on first run so every
# variable is documented and editable in one place. Existing `.env` files are
# never overwritten. For quick tests, `.env.example` duplicates all defaults
# and can be copied as-is: `Copy-Item .env.example .env`.
$envTemplate = Join-Path $RepoRoot ".env.example"
$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile) -and (Test-Path $envTemplate)) {
    Copy-Item $envTemplate $envFile
    Write-Host ".env created from .env.example (stock test values; customise as needed)."
}

function Step([int]$n, [string]$msg) {
    Write-Host "`n=== [$n/4] $msg ===" -ForegroundColor Cyan
}

# ---------------------------------------------------------------- 1. Docker --
Step 1 "Docker engine"
docker info *> $null
$dockerReady = ($LASTEXITCODE -eq 0)
if (-not $dockerReady) {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerDesktop) {
        Write-Host "Docker engine not running - starting Docker Desktop ..."
        Start-Process $dockerDesktop
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Seconds 2
            docker info *> $null
            if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
        }
    }
    if (-not $dockerReady) {
        throw "Docker is unavailable. Install Docker Desktop (https://www.docker.com/products/docker-desktop/) and re-run."
    }
}
Write-Host "Docker engine OK."

# ------------------------------------------------------- 2. Demo stack up ----
Step 2 "Demo stack (backend + frontend + tunnel$(if (-not $SkipVoice) { ' + STT voice' }))"
Push-Location $RepoRoot
try {
    # All compose services start by default; -SkipVoice starts everything
    # except stt (typed chat never needs it).
    $composeArgs = @("compose", "up", "-d", "--build")
    if ($SkipVoice) { $composeArgs += @("backend", "frontend", "tunnel") }
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed (exit $LASTEXITCODE)." }
} finally { Pop-Location }

Write-Host "Waiting for backend health (http://localhost:8000/api/health) ..."
$health = $null
for ($i = 0; $i -lt 90; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 5
        break
    } catch { Start-Sleep -Seconds 2 }
}
if ($null -eq $health) {
    Write-Warning "Backend did not answer /api/health in time. Check: docker compose logs backend"
} else {
    Write-Host "Backend OK (data_source: $($health.data_source))."
}

# ------------------------------------------------------------- 3. Tunnel -----
Step 3 "Dify Cloud tool tunnel (public URL)"
# Self-heal: Cloudflare revokes idle quick tunnels server-side while the
# container keeps retrying a dead registration ("Tunnel not found"). If the
# known URL is dead, restart the service so cloudflared mints a fresh one.
$existing = Get-TunnelUrl
if ($existing -and -not (Test-TunnelHealth $existing 10)) {
    Write-Host "Existing tunnel URL is dead ($existing) - restarting the tunnel service ..." -ForegroundColor Yellow
    Push-Location $RepoRoot
    try { docker compose restart tunnel | Out-Null } finally { Pop-Location }
}
$tunnelUrl = Wait-Tunnel -TimeoutSec 180
if (-not $tunnelUrl) {
    Write-Warning "No healthy tunnel URL yet. Check:  docker compose logs tunnel"
    Write-Warning "Without a tunnel, Dify Cloud tool calls fail (the agent falls back"
    Write-Warning "to its guardrail message); the frontend's deterministic chat still works."
} else {
    Write-Host "Tunnel OK: $tunnelUrl" -ForegroundColor Green
    Save-TunnelUrl $tunnelUrl
    $specUrl = Get-OpenapiServerUrl
    if ($specUrl -ne $tunnelUrl) {
        if (Set-OpenapiServerUrl $tunnelUrl) {
            Write-Host "dify/openapi.yaml servers[0].url updated:" -ForegroundColor Yellow
            Write-Host "  old: $specUrl" -ForegroundColor Yellow
            Write-Host "  new: $tunnelUrl" -ForegroundColor Yellow
            Write-Host "ACTION REQUIRED: re-sync the tool in Dify (Integrations -> Tools ->" -ForegroundColor Yellow
            Write-Host "Swagger API -> paste the updated dify/openapi.yaml) and republish the app." -ForegroundColor Yellow
        }
    } else {
        Write-Host "dify/openapi.yaml already points at this tunnel URL."
    }
}

# ------------------------------------------- 4. Verify + service summary -----
Step 4 "Verification + service summary"
& (Join-Path $PSScriptRoot "verify_infra.ps1")
$verifyExit = $LASTEXITCODE

# ---- Service summary --------------------------------------------------------
$chatbotUrl = ""
foreach ($envFile in @((Join-Path $RepoRoot ".env"), (Join-Path $RepoRoot "frontend\.env"))) {
    if (Test-Path $envFile) {
        $m = [regex]::Match((Get-Content $envFile -Raw), '(?m)^\s*VITE_DIFY_CHATBOT_URL\s*=\s*(\S+)')
        if ($m.Success -and $m.Groups[1].Value) { $chatbotUrl = $m.Groups[1].Value; break }
    }
}
if (-not $chatbotUrl) { $chatbotUrl = "https://udify.app  (compose default)" }

Write-Host "`n=== Services ===" -ForegroundColor Cyan
Write-Host ("  Analytics API      http://localhost:8000/api/health")
Write-Host ("  Web UI             http://localhost:5173")
if (-not $SkipVoice) { Write-Host ("  Voice STT          http://localhost:8100  (included by default; -SkipVoice leaves it out)") }
Write-Host ("  Dify tool tunnel   $tunnelUrl")
Write-Host ("  Dify chatbot       $chatbotUrl")
Write-Host "`n=== Dify workspace expectations (configure once, browser) ===" -ForegroundColor Cyan
Write-Host "  Model provider:    Groq (free key) -> agent model gpt-oss-120b"
Write-Host "  Speech-to-Text:    whisper-large-v3-turbo (free, optional voice)"
Write-Host "  Full walkthrough:  dify\README.md"
Write-Host "  Model smoke test:  scripts\verify_infra.ps1 -DifyApiKey <app API key>"
Write-Host "`nBootstrap finished." -ForegroundColor Green
exit $verifyExit