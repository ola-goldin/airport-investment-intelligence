#requires -Version 5.1
<#
.SYNOPSIS
  Read-only infrastructure verification for the Airport Investment Intelligence
  Agent. Safe to run at any time; makes no changes.

.DESCRIPTION
  Checks: demo stack (backend / deterministic spot-check / frontend), the
  public Dify tool tunnel, the optional local STT service, the Dify embed
  URL configuration + reachability, and dify/openapi.yaml tunnel sync.
  Prints a PASS/FAIL/WARN report and exits non-zero if a CORE check fails.
  -RunTests additionally runs the backend pytest suite.
  -DifyApiKey (or env DIFY_API_KEY) smoke-tests the actual Dify model via
  the Service API (blocking chat) - that check is CORE when the key is set.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\verify_infra.ps1
  powershell -ExecutionPolicy Bypass -File scripts\verify_infra.ps1 -RunTests
  powershell -ExecutionPolicy Bypass -File scripts\verify_infra.ps1 -DifyApiKey <key>
#>
param(
    [switch]$RunTests,
    [string]$DifyApiKey = $env:DIFY_API_KEY
)
$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "tunnel.ps1")
$ProgressPreference = "SilentlyContinue"   # suppress Invoke-WebRequest progress spam
$script:exitCode = 0

function Check([string]$Name, [string]$Tier, [scriptblock]$Test, [string]$Hint) {
    try {
        & $Test
        Write-Host ("  PASS  {0}" -f $Name) -ForegroundColor Green
    } catch {
        if ($Tier -eq "CORE") {
            $script:exitCode = 1
            Write-Host ("  FAIL  {0}" -f $Name) -ForegroundColor Red
        } else {
            Write-Host ("  WARN  {0}" -f $Name) -ForegroundColor Yellow
        }
        Write-Host ("        {0}" -f $_.Exception.Message) -ForegroundColor DarkGray
        if ($Hint) { Write-Host ("        fix: {0}" -f $Hint) -ForegroundColor DarkGray }
    }
}

function Assert([bool]$Cond, [string]$Msg) { if (-not $Cond) { throw $Msg } }

Write-Host "Infrastructure verification - $RepoRoot`n"

# --- Backend ----------------------------------------------------------------
$script:health = $null
Check "Backend :8000 /api/health" "CORE" {
    $script:health = Invoke-RestMethod "http://localhost:8000/api/health" -TimeoutSec 10
    Assert ($null -ne $script:health) "no JSON returned"
    Write-Host ("        data_source={0}" -f $script:health.data_source) -ForegroundColor DarkGray
} "docker compose up -d (repo root); logs: docker compose logs backend"

Check "Deterministic spot-check: New England ranking contains BOS" "CORE" {
    $rank = Invoke-RestMethod "http://localhost:8000/api/airports/rank" -Method Post `
             -Body '{"region":"New England"}' -ContentType "application/json" -TimeoutSec 20
    $codes = @()
    # Real response shape: { region, scope, ranking: [ { airport, ... } ], assumptions }
    foreach ($item in @($rank.ranking) + @($rank.rankings) + @($rank.results) + @($rank)) {
        if ($item.airport) { $codes += $item.airport }
        elseif ($item.code) { $codes += $item.code }
    }
    Assert ($codes -contains "BOS") "BOS missing from ranking response"
} "docker compose logs backend - data layer may have failed to load."

# --- Frontend / tunnel ------------------------------------------------------
Check "Frontend :5173 serves the UI" "CORE" {
    $r = Invoke-WebRequest "http://localhost:5173" -TimeoutSec 10 -UseBasicParsing
    Assert ($r.StatusCode -eq 200) "HTTP $($r.StatusCode)"
} "docker compose up -d (repo root)."

Check "Dify tool tunnel: public URL answers /api/health" "CORE" {
    $script:tunnelUrl = Get-TunnelUrl
    Assert (-not [string]::IsNullOrWhiteSpace($script:tunnelUrl)) "no tunnel URL found (data\tunnel_url.txt empty and no URL in compose logs)"
    Assert (Test-TunnelHealth $script:tunnelUrl 15) "tunnel URL not reachable or backend down: $($script:tunnelUrl)"
    Write-Host ("        {0}" -f $script:tunnelUrl) -ForegroundColor DarkGray
} "docker compose up -d (starts the 'tunnel'); if its URL is stale/dead run: docker compose restart tunnel; logs: docker compose logs tunnel; full repair: scripts\setup_infra.ps1"

Check "Local Whisper STT :8100 (mic button for the fallback chat)" "BONUS" {
    $r = Invoke-WebRequest "http://localhost:8100/health" -TimeoutSec 10 -UseBasicParsing
    Assert ($r.StatusCode -eq 200) "HTTP $($r.StatusCode)"
    $h = $r.Content | ConvertFrom-Json
    Assert ($h.import_ok -eq $true) "faster-whisper not installed in the STT service"
    if ($h.model_loaded) {
        Write-Host ("        engine={0} model={1} (loaded, ready)" -f $h.engine, $h.model) -ForegroundColor DarkGray
    } else {
        Write-Host ("        engine={0} model={1} (downloads on first mic use)" -f $h.engine, $h.model) -ForegroundColor DarkGray
    }
} "docker compose up -d (stt starts with the stack); smaller model: STT_MODEL_SIZE=tiny docker compose up -d --build stt"

# --- Dify embed configuration ------------------------------------------------
Check "Dify embed URL configured (chatbot for the iframe)" "BONUS" {
    $script:embedUrl = ""
    foreach ($envFile in @((Join-Path $RepoRoot ".env"), (Join-Path $RepoRoot "frontend\.env"))) {
        if (Test-Path $envFile) {
            $m = [regex]::Match((Get-Content $envFile -Raw), '(?m)^\s*VITE_DIFY_CHATBOT_URL\s*=\s*(\S+)')
            if ($m.Success -and $m.Groups[1].Value) { $script:embedUrl = $m.Groups[1].Value; break }
        }
    }
    if (-not $script:embedUrl) {
        $script:embedUrl = "https://udify.app/chatbot/UfdIIKocvyo9IdrW"
        Write-Host "        no value in .env files - docker compose default applies" -ForegroundColor DarkGray
    }
    Assert ($script:embedUrl -match "^https?://") "does not look like a URL: $($script:embedUrl)"
    Write-Host ("        {0}" -f $script:embedUrl) -ForegroundColor DarkGray
} "Set VITE_DIFY_CHATBOT_URL in frontend\.env (or a root .env), then: docker compose up -d"

Check "Dify chatbot reachable (published app responds)" "BONUS" {
    Assert (-not [string]::IsNullOrWhiteSpace($script:embedUrl)) "embed URL unknown - run the config check first"
    $r = Invoke-WebRequest $script:embedUrl -TimeoutSec 20 -UseBasicParsing
    Assert ($r.StatusCode -eq 200) "HTTP $($r.StatusCode)"
} "Open the URL in a browser; in Dify: App -> Publish (republish after changes)."

Check "dify/openapi.yaml synced with the live tunnel URL" "BONUS" {
    $live = Get-TunnelUrl
    Assert (-not [string]::IsNullOrWhiteSpace($live)) "no live tunnel URL (see the tunnel check above)"
    $spec = Get-OpenapiServerUrl
    Assert (-not [string]::IsNullOrWhiteSpace($spec)) "dify/openapi.yaml not found or has no servers[0].url"
    Assert ($spec -eq $live) "spec points at '$spec' but the live tunnel is '$live'"
} "Run scripts\setup_infra.ps1 to auto-sync dify/openapi.yaml, then re-paste it in Dify (Integrations -> Tools) and republish the app."

# --- Optional: real model smoke test (needs the app's Service API key) -------
if ($DifyApiKey) {
    Check "Dify model responds (blocking chat via Service API)" "CORE" {
        $u = if ($script:embedUrl) { $script:embedUrl } else { "https://udify.app" }
        $hostName = ([uri]$u).Host
        $body = @{
            inputs         = @{}
            query          = "Reply with exactly: OK"
            response_mode  = "blocking"
            user           = "infra-verify"
        } | ConvertTo-Json -Compress
        $resp = Invoke-RestMethod -Method Post -Uri "https://$hostName/api/v1/chat-messages" `
            -Headers @{ Authorization = "Bearer $DifyApiKey" } `
            -ContentType "application/json" -Body $body -TimeoutSec 90
        Assert (-not [string]::IsNullOrWhiteSpace([string]$resp.answer)) "200 OK but no 'answer' field: $($resp | ConvertTo-Json -Compress -Depth 3)"
        $preview = $resp.answer.Trim()
        if ($preview.Length -gt 80) { $preview = $preview.Substring(0, 80) + "..." }
        Write-Host "        model answered: $preview" -ForegroundColor DarkGray
    } "Check the key (Dify: App -> API Access), the model provider (Integrations -> Model Provider), and that the workspace has free credits/a Groq key."
}

# --- Optional: backend tests -------------------------------------------------
if ($RunTests) {
    Check "Backend pytest suite" "CORE" {
        Push-Location $RepoRoot
        try {
            python -m pytest backend\tests -q
            Assert ($LASTEXITCODE -eq 0) "pytest exited with $LASTEXITCODE"
        } finally { Pop-Location }
    } "See failing output above; tests are the fastest correctness signal."
}

# --- Final report ------------------------------------------------------------
Write-Host ""
if ($script:exitCode -eq 0) {
    Write-Host "All CORE checks passed - demo usable (text fallback works even if bonus items are missing)." -ForegroundColor Green
} else {
    Write-Host "One or more CORE checks failed - fix the FAIL rows above." -ForegroundColor Red
}
Write-Host "NOTICE  Dify workspace (browser, configure once):" -ForegroundColor Cyan
Write-Host "        model  -> gpt-oss-120b via Groq free key (Integrations -> Model Provider)" -ForegroundColor Cyan
Write-Host "        STT    -> whisper-large-v3-turbo (optional voice)" -ForegroundColor Cyan
Write-Host "        smoke  -> run again with -DifyApiKey <app API key> to verify the model answers" -ForegroundColor Cyan
Write-Host "        tunnel -> after EVERY tunnel URL change: re-sync the tool in Dify + republish" -ForegroundColor Cyan
exit $script:exitCode