[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stateFile = Join-Path $PSScriptRoot ".run\services.json"
$composeFile = Join-Path $root "infra\compose\docker-compose.yml"
$envFile = Join-Path $root ".env"

if (Test-Path $stateFile) {
    $state = Get-Content $stateFile -Raw | ConvertFrom-Json
    foreach ($entry in $state.processes) {
        $process = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if (-not $process) { continue }

        # Do not stop an unrelated process if Windows has reused the PID.
        $actualStart = $process.StartTime.ToUniversalTime()
        $recordedStart = [DateTime]::Parse($entry.startedAt).ToUniversalTime()
        if ([Math]::Abs(($actualStart - $recordedStart).TotalSeconds) -lt 2) {
            Write-Host "Stopping $($entry.name) (PID $($entry.pid))..."
            & taskkill.exe /PID $entry.pid /T /F 2>$null | Out-Null
        }
        else {
            Write-Warning "$($entry.name) PID was reused by another process; it was not stopped."
        }
    }
    Remove-Item $stateFile -Force
}
else {
    Write-Host "No recorded backend/frontend processes were found."
}

$composeArguments = @("compose")
if (Test-Path $envFile) { $composeArguments += @("--env-file", $envFile) }
$composeArguments += @("-f", $composeFile, "down")
& docker @composeArguments
if ($LASTEXITCODE -ne 0) { throw "Failed to stop Docker Compose services." }

Write-Host "All services stopped." -ForegroundColor Green
