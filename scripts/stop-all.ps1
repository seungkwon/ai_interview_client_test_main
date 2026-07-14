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

        # PID가 재사용된 경우 관련 없는 프로세스를 종료하지 않는다.
        $actualStart = $process.StartTime.ToUniversalTime()
        $recordedStart = [DateTime]::Parse($entry.startedAt).ToUniversalTime()
        if ([Math]::Abs(($actualStart - $recordedStart).TotalSeconds) -lt 2) {
            Write-Host "$($entry.name) 종료 중 (PID $($entry.pid))..."
            & taskkill.exe /PID $entry.pid /T /F 2>$null | Out-Null
        }
        else {
            Write-Warning "$($entry.name)의 PID가 다른 프로세스에 재사용되어 종료하지 않았습니다."
        }
    }
    Remove-Item $stateFile -Force
}
else {
    Write-Host "기록된 backend/frontend 프로세스가 없습니다."
}

$composeArguments = @("compose")
if (Test-Path $envFile) { $composeArguments += @("--env-file", $envFile) }
$composeArguments += @("-f", $composeFile, "down")
& docker @composeArguments
if ($LASTEXITCODE -ne 0) { throw "Docker Compose 정지에 실패했습니다." }

Write-Host "모든 서비스를 정지했습니다." -ForegroundColor Green
