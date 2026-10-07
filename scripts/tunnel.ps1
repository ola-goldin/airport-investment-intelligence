# Shared tunnel helpers for setup_infra.ps1 / verify_infra.ps1.
# Dot-source:  . (Join-Path $PSScriptRoot "tunnel.ps1")
# All functions are read-only except Set-TunnelUrlFiles (bookkeeping sync).

$script:UrlPattern = 'https://[a-z0-9-]+\.trycloudflare\.com'
$script:TunnelUrlFile = Join-Path (Split-Path -Parent $PSScriptRoot) "data\tunnel_url.txt"
$script:OpenapiFile = Join-Path (Split-Path -Parent $PSScriptRoot) "dify\openapi.yaml"

# Parse the public URL out of the compose tunnel container logs.
# Takes the LAST banner: a restarted tunnel process appends a new URL while
# the old (dead) one stays earlier in the logs.
function Get-TunnelUrlFromLogs() {
    try {
        $logs = docker compose logs tunnel --no-log-prefix --tail 400 2>$null
        $last = $null
        foreach ($line in @($logs)) {
            if ($line -match $script:UrlPattern) { $last = $Matches[0] }
        }
        return $last
    } catch { }
    return $null
}

# Live URL: compose logs first (authoritative), then the saved file.
function Get-TunnelUrl() {
    $u = Get-TunnelUrlFromLogs
    if ($u) { return $u }
    if (Test-Path $script:TunnelUrlFile) {
        $saved = (Get-Content $script:TunnelUrlFile -Raw -ErrorAction SilentlyContinue)
        if ($saved) { return $saved.Trim() }
    }
    return $null
}

function Get-OpenapiServerUrl() {
    if (-not (Test-Path $script:OpenapiFile)) { return $null }
    $m = [regex]::Match((Get-Content $script:OpenapiFile -Raw -Encoding UTF8), '(?m)^\s*-\s*url:\s*(\S+)')
    if ($m.Success) { return $m.Groups[1].Value }
    return $null
}

# Point dify/openapi.yaml servers[0].url at $Url (first "- url:" entry only).
function Set-OpenapiServerUrl([string]$Url) {
    $text = Get-Content $script:OpenapiFile -Raw -Encoding UTF8
    $new = [regex]::Replace($text, '(?m)^(\s*-\s*url:\s*)\S+', ('$1' + $Url), 1)
    if ($new -ne $text) {
        [System.IO.File]::WriteAllText($script:OpenapiFile, $new,
            (New-Object System.Text.UTF8Encoding($false)))
        return $true
    }
    return $false
}

# Save the live URL where check_tunnel.py expects it.
function Save-TunnelUrl([string]$Url) {
    $dir = Split-Path -Parent $script:TunnelUrlFile
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    [System.IO.File]::WriteAllText($script:TunnelUrlFile, $Url)
}

# Probe <Url>/api/health; $true when the tunnel reaches the backend.
function Test-TunnelHealth([string]$Url, [int]$TimeoutSec = 15) {
    if (-not $Url) { return $false }
    try {
        $ProgressPreference = "SilentlyContinue"
        $r = Invoke-RestMethod ($Url.TrimEnd('/') + "/api/health") -TimeoutSec $TimeoutSec
        return ($null -ne $r -and $r.status -eq "ok")
    } catch { return $false }
}

# Wait until the tunnel URL exists AND answers /api/health through the public
# internet. Returns the URL, or $null on timeout.
function Wait-Tunnel([int]$TimeoutSec = 180) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $u = Get-TunnelUrlFromLogs
        if ($u -and (Test-TunnelHealth $u)) { return $u }
        Start-Sleep -Seconds 3
    }
    return $null
}