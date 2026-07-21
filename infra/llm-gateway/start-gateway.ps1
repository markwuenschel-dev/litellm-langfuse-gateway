# Bring the LiteLLM gateway stack up and verify it is listening.
# Registered as the "LiteLLM Gateway Autostart" scheduled task (at logon), so the
# gateway survives computer shutdown/restart without manual steps. Idempotent —
# safe to run any time; compose up -d is a no-op when the stack is already up.
#
# Compose is run with cwd = this directory so .env here is the interpolation
# source (see the env-origin warning in ../../docker-compose.yml).

$ErrorActionPreference = "Continue"
$gatewayDir = $PSScriptRoot
$dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$healthUrl = "http://localhost:4000/health/liveliness"
$log = Join-Path $env:LOCALAPPDATA "litellm-gateway-autostart.log"

function Write-Log($msg) {
    "$(Get-Date -Format o)  $msg" | Add-Content $log
}

function Test-Engine {
    docker info *> $null
    return ($LASTEXITCODE -eq 0)
}

Write-Log "--- autostart run ---"

# 1. Docker engine: start Docker Desktop if the engine is unreachable, then wait.
if (-not (Test-Engine)) {
    if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
        Write-Log "Docker Desktop not running - launching it"
        Start-Process $dockerDesktop
    }
    $deadline = (Get-Date).AddMinutes(5)
    while (-not (Test-Engine)) {
        if ((Get-Date) -gt $deadline) {
            Write-Log "FAIL: Docker engine not reachable after 5 minutes"
            exit 1
        }
        Start-Sleep -Seconds 5
    }
}
Write-Log "Docker engine is up"

# 2. Stack up (idempotent). cwd = infra/llm-gateway so the right .env is used.
Set-Location $gatewayDir
docker compose -f compose.yaml up -d 2>&1 | ForEach-Object { Write-Log "compose: $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Log "FAIL: docker compose up exited with $LASTEXITCODE"
    exit 1
}

# 3. Wait until the gateway actually answers on its port.
$deadline = (Get-Date).AddMinutes(3)
$healthy = $false
while (-not $healthy) {
    try {
        Invoke-WebRequest $healthUrl -UseBasicParsing -TimeoutSec 5 | Out-Null
        Write-Log "OK: gateway listening ($healthUrl)"
        $healthy = $true
    } catch {
        if ((Get-Date) -gt $deadline) {
            Write-Log "FAIL: gateway not healthy after 3 minutes"
            exit 1
        }
        Start-Sleep -Seconds 5
    }
}

# 4. Key-registry smoke. Virtual keys are rows in the Postgres volume, not
#    self-validating tokens - recreating the volume (llg down -v, volume prune,
#    re-provision) silently orphans every consumer-held key (401
#    token_not_found_in_db). Log the alias inventory each boot so staleness has
#    a paper trail, and warn loudly when the registry is empty. Aliases only -
#    never tokens or the master key.
$masterKey = (Get-Content (Join-Path $gatewayDir ".env") |
    Where-Object { $_ -match "^LITELLM_MASTER_KEY=" } |
    Select-Object -First 1) -replace "^LITELLM_MASTER_KEY=", ""
if (-not $masterKey) {
    Write-Log "WARN: LITELLM_MASTER_KEY not found in .env - skipping key-registry smoke"
    exit 0
}
try {
    $resp = Invoke-RestMethod "http://localhost:4000/key/list?page=1&size=100&return_full_object=true" `
        -Headers @{ Authorization = "Bearer $masterKey" } -TimeoutSec 15
    $aliases = @($resp.keys | ForEach-Object { if ($_ -is [string]) { "<no-alias>" } else { $_.key_alias } })
    Write-Log "Key registry: $($aliases.Count) key(s): $($aliases -join ', ')"
    if ($aliases.Count -eq 0) {
        Write-Log "WARN: key registry is EMPTY. If the Postgres volume was recreated, every virtual key stored in consumer .env files is now orphaned (requests fail 401 token_not_found_in_db). Re-mint with: uv run llg keys create --key-alias <service>-dev"
    }
} catch {
    Write-Log "WARN: key-registry smoke failed (gateway is up, inventory unknown): $($_.Exception.Message)"
}
exit 0
