$ErrorActionPreference = 'SilentlyContinue'

$root = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $root '.run'
$stopped = $false

foreach ($name in @('api', 'scheduler', 'frontend')) {
    $pidFile = Join-Path $runDir "$name.pid"

    if (-not (Test-Path $pidFile)) {
        continue
    }

    $pidValue = Get-Content $pidFile | Select-Object -First 1
    if ($pidValue -match '^\d+$') {
        taskkill.exe /PID $pidValue /T /F *> $null
        Write-Host "$name stopped (PID $pidValue)."
        $stopped = $true
    }

    Remove-Item $pidFile -Force
}

if (-not $stopped) {
    Write-Host 'No bili-update processes were recorded as running.'
}
