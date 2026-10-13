param([switch]$WslDependencies)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeDir = Join-Path $projectRoot '.local'
$logDir = Join-Path $runtimeDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if ($WslDependencies) {
    $scriptPath = (Join-Path $PSScriptRoot 'start-wsl-deps.sh').Replace('\', '/')
    $linuxScript = (wsl -d Ubuntu-22.04 -- wslpath -a $scriptPath).Trim()
    wsl -d Ubuntu-22.04 -- bash $linuxScript
    if ($LASTEXITCODE -ne 0) { throw 'Local dependencies did not start.' }
}
$python = Join-Path $projectRoot 'backend/.venv/Scripts/python.exe'
$node = (Get-Command node).Source
if (-not (Test-Path -LiteralPath $python)) { throw 'Backend is not installed. Follow README.md first.' }
$statePath = Join-Path $runtimeDir 'processes.json'
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $live = @($state | Where-Object { Get-Process -Id $_.pid -ErrorAction SilentlyContinue })
    if ($live.Count -gt 0) { throw 'Recorded processes are still running. Use scripts/stop-local.ps1 before restarting.' }
}
$started = @()
try {
    $api = Start-Process -FilePath $python -ArgumentList '-m uvicorn iwardrobe.main:app --host 127.0.0.1 --port 18765' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'api.log') -RedirectStandardError (Join-Path $logDir 'api.error.log')
    $started += @{name='api'; pid=$api.Id}
    $worker = Start-Process -FilePath $python -ArgumentList '-m iwardrobe.worker' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'worker.log') -RedirectStandardError (Join-Path $logDir 'worker.error.log')
    $started += @{name='worker'; pid=$worker.Id}
    $vite = Join-Path $projectRoot 'apps/web/node_modules/vite/bin/vite.js'
    $web = Start-Process -FilePath $node -ArgumentList @('"' + $vite + '"', '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory (Join-Path $projectRoot 'apps/web') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'web.log') -RedirectStandardError (Join-Path $logDir 'web.error.log')
    $started += @{name='web'; pid=$web.Id}
    $started | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
    $ready = $false
    for ($attempt = 0; $attempt -lt 25; $attempt++) {
        Start-Sleep -Milliseconds 400
        if ($started | Where-Object { -not (Get-Process -Id $_.pid -ErrorAction SilentlyContinue) }) { throw 'A service exited. See .local/logs.' }
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:18765/api/health' -TimeoutSec 2
            $page = Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2
            if ($health.database -eq 'ok' -and $page.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { throw 'Startup timed out. See .local/logs.' }
    Write-Output 'IWardrobe is running at http://127.0.0.1:5173'
    Write-Output 'Demo credentials: .local/demo-accounts.json'
    Write-Output 'Stop: powershell -ExecutionPolicy Bypass -File scripts/stop-local.ps1'
} catch {
    foreach ($entry in $started) { Stop-Process -Id $entry.pid -ErrorAction SilentlyContinue }
    throw
}
