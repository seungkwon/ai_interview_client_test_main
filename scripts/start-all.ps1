[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stateDirectory = Join-Path $PSScriptRoot ".run"
$stateFile = Join-Path $stateDirectory "services.json"
$composeFile = Join-Path $root "infra\compose\docker-compose.yml"
$envFile = Join-Path $root ".env"
$backendDirectory = Join-Path $root "backend"
$frontendDirectory = Join-Path $root "frontend"
$python = Join-Path $backendDirectory ".venv\Scripts\python.exe"
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
$docker = (Get-Command docker.exe -ErrorAction SilentlyContinue).Source
$requirements = Join-Path $backendDirectory "requirements\base.txt"

function Import-DotEnv([string]$Path) {
    if (-not (Test-Path $Path)) { return }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) { continue }
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if (Test-Path $stateFile) {
    throw "Services appear to be running already. Run scripts\stop-all.ps1 first."
}

# Bootstrap the backend on first run. Prefer `python`, then the Windows `py` launcher.
if (-not (Test-Path $python)) {
    $systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
    $pythonArguments = @("-m", "venv", (Join-Path $backendDirectory ".venv"))

    if (-not $systemPython) {
        $systemPython = Get-Command py.exe -ErrorAction SilentlyContinue
        $pythonArguments = @("-3", "-m", "venv", (Join-Path $backendDirectory ".venv"))
    }
    if (-not $systemPython) {
        throw "Python was not found. Install Python 3 and ensure python.exe or py.exe is in PATH."
    }

    Write-Host "Backend virtual environment not found. Creating .venv..." -ForegroundColor Yellow
    & $systemPython.Source @pythonArguments
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $python)) {
        throw "Failed to create the backend virtual environment."
    }

    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    & $python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install backend dependencies from $requirements."
    }
}

if (-not (Test-Path $python)) {
    throw "Backend virtual environment is unavailable: $python"
}
if (-not $npm) {
    throw "npm.cmd was not found. Install Node.js/npm and ensure it is in PATH."
}
if (-not $docker) {
    throw "docker.exe was not found. Install Docker Desktop and ensure it is in PATH."
}
if (-not (Test-Path (Join-Path $frontendDirectory "node_modules"))) {
    Write-Host "Frontend dependencies not found. Running npm install..." -ForegroundColor Yellow
    Push-Location $frontendDirectory
    try {
        & $npm install
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install frontend dependencies."
        }
    }
    finally {
        Pop-Location
    }
}

Import-DotEnv $envFile
New-Item -ItemType Directory -Force -Path $stateDirectory | Out-Null

$started = @()
try {
    $composeArguments = @("compose")
    if (Test-Path $envFile) { $composeArguments += @("--env-file", $envFile) }
    $composeArguments += @("-f", $composeFile, "up", "-d")
    & docker @composeArguments
    if ($LASTEXITCODE -ne 0) { throw "Failed to start Docker Compose services." }

    $backendArgs = @("-m", "uvicorn", "app.main:app", "--reload")
    if ($env:BACKEND_HOST) { $backendArgs += @("--host", $env:BACKEND_HOST) }
    if ($env:BACKEND_PORT) { $backendArgs += @("--port", $env:BACKEND_PORT) }
    $backend = Start-Process -FilePath $python -ArgumentList $backendArgs -WorkingDirectory $backendDirectory -PassThru
    $started += $backend

    $frontend = Start-Process -FilePath $npm -ArgumentList @("run", "dev") -WorkingDirectory $frontendDirectory -PassThru
    $started += $frontend

    $state = @{
        createdAt = (Get-Date).ToUniversalTime().ToString("o")
        processes = @($started | ForEach-Object {
            @{ name = if ($_.Id -eq $backend.Id) { "backend" } else { "frontend" }; pid = $_.Id; startedAt = $_.StartTime.ToUniversalTime().ToString("o") }
        })
    }
    $state | ConvertTo-Json -Depth 4 | Set-Content -Path $stateFile -Encoding UTF8

    $backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
    $frontendUrl = if ($env:FRONTEND_DEV_SERVER_URL) { $env:FRONTEND_DEV_SERVER_URL } else { "http://localhost:5173" }
    Write-Host "All services started." -ForegroundColor Green
    Write-Host "  Backend : http://localhost:$backendPort"
    Write-Host "  Frontend: $frontendUrl"
    Write-Host "Stop: .\scripts\stop-all.cmd"
}
catch {
    foreach ($process in $started) {
        if (-not $process.HasExited) { & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
    }
    & docker compose -f $composeFile down 2>$null | Out-Null
    Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
    throw
}
