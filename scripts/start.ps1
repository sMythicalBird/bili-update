$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $root '.run'
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$backendLogs = Join-Path $backend 'logs'
$frontendLogs = Join-Path $frontend 'logs'

$null = New-Item -ItemType Directory -Force -Path $runDir, $backendLogs, $frontendLogs

function Start-ServiceProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$LogDirectory
    )

    $pidFile = Join-Path $runDir "$Name.pid"

    if (Test-Path $pidFile) {
        $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($oldPid -and (Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue)) {
            Write-Host "$Name is already running (PID $oldPid)."
            return [int]$oldPid
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }

    $stdout = Join-Path $LogDirectory "$Name.out.log"
    $stderr = Join-Path $LogDirectory "$Name.err.log"
    $process = Start-Process `
        -FilePath 'cmd.exe' `
        -ArgumentList @('/d', '/c', "$Command < NUL") `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru

    Set-Content -Path $pidFile -Value $process.Id -Encoding ascii
    Write-Host "$Name started (PID $($process.Id))."
    return $process.Id
}

Write-Host 'Starting bili-update in background...'

$apiPid = Start-ServiceProcess `
    -Name 'api' `
    -WorkingDirectory $backend `
    -Command 'uv run python -m src.main --web' `
    -LogDirectory $backendLogs

$schedulerPid = Start-ServiceProcess `
    -Name 'scheduler' `
    -WorkingDirectory $backend `
    -Command 'uv run python -m src.main' `
    -LogDirectory $backendLogs

$frontendPid = Start-ServiceProcess `
    -Name 'frontend' `
    -WorkingDirectory $frontend `
    -Command 'pnpm run dev --host 127.0.0.1' `
    -LogDirectory $frontendLogs

Write-Host ''
Write-Host 'Frontend: http://localhost:5173'
Write-Host 'API:      http://127.0.0.1:5000'
Write-Host "PIDs:     api=$apiPid scheduler=$schedulerPid frontend=$frontendPid"
Write-Host 'Logs:     backend/logs and frontend/logs'
