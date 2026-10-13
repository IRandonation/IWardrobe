$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$statePath = Join-Path $projectRoot '.local/processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Output 'No recorded IWardrobe processes.'; exit 0 }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($entry in $state) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.pid)" -ErrorAction SilentlyContinue
    if ($process -and ($process.ExecutablePath.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase) -or $process.CommandLine.Contains($projectRoot))) {
        Stop-Process -Id $entry.pid
        Write-Output "Stopped $($entry.name)."
    } elseif ($process) { throw "Process ID $($entry.pid) no longer belongs to this project; it was not stopped." }
}
Remove-Item -LiteralPath $statePath
