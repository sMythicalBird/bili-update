@echo off
setlocal
set "ROOT=%~dp0.."

echo ========================================
echo bili-update environment initialization
echo ========================================

where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] uv not found. Installing uv from the official installer...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [ERROR] uv installation failed.
        exit /b 1
    )
    if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

where node >nul 2>&1
if errorlevel 1 (
    echo [INFO] Node.js not found. Installing Node.js LTS with winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] winget is not available. Install Node.js LTS manually: https://nodejs.org/
        exit /b 1
    )
    winget install --id OpenJS.NodeJS.LTS --exact --accept-source-agreements --accept-package-agreements
    if errorlevel 1 exit /b 1
    echo [INFO] Node.js was installed. Please open a new terminal and run this script again.
    exit /b 0
)

where corepack >nul 2>&1
if not errorlevel 1 (
    corepack enable >nul 2>&1
    corepack prepare pnpm@latest --activate >nul 2>&1
)
where pnpm >nul 2>&1
if errorlevel 1 call npm install --global pnpm

cd /d "%ROOT%\backend"
uv python install 3.12
if errorlevel 1 exit /b 1
uv sync
if errorlevel 1 exit /b 1

cd /d "%ROOT%\frontend"
call pnpm install
if errorlevel 1 exit /b 1

echo.
echo Initialization complete. Run scripts\start.ps1 to start the application.
endlocal
