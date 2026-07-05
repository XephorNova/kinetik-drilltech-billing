@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

echo ==============================================
echo  Kinetik Drilltech Billing - Dev Startup
echo ==============================================
echo.

REM --- Resolve npm (works even if PATH hasn't picked up a fresh Node/Volta install yet) ---
where npm >nul 2>&1
if errorlevel 1 (
    set "NPM=C:\Program Files\Volta\npm.cmd"
) else (
    set "NPM=npm"
)

REM --- Check MongoDB is reachable on the default port ---
netstat -an | find "LISTENING" | find ":27017" >nul
if errorlevel 1 (
    echo [WARN] Nothing is listening on port 27017 - make sure MongoDB is running.
) else (
    echo [OK] MongoDB detected on port 27017.
)

REM --- Backend .env ---
if not exist "%BACKEND%\.env" (
    copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
    echo [INFO] Created backend\.env from .env.example - edit JWT_SECRET/ADMIN_PASSWORD before real use.
)

REM --- Backend venv ---
if not exist "%BACKEND%\.venv\Scripts\uvicorn.exe" (
    echo [ERROR] backend\.venv not found or incomplete.
    echo         Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements-dev.txt
    pause
    exit /b 1
)

REM --- Frontend .env ---
if not exist "%FRONTEND%\.env" (
    copy "%FRONTEND%\.env.example" "%FRONTEND%\.env" >nul
    echo [INFO] Created frontend\.env from .env.example
)

REM --- Frontend deps ---
if not exist "%FRONTEND%\node_modules" (
    echo [INFO] Installing frontend dependencies, this may take a minute...
    pushd "%FRONTEND%"
    call "%NPM%" install
    popd
)

echo.
echo Starting backend  - http://localhost:8000
start "Billing Backend" cmd /k "cd /d "%BACKEND%" && .venv\Scripts\uvicorn.exe app.main:app --reload --port 8000"

echo Starting frontend - http://localhost:5173
start "Billing Frontend" cmd /k "cd /d "%FRONTEND%" && "%NPM%" run dev"

echo.
echo Both services are starting in separate windows.
echo Close those windows (or Ctrl+C inside them) to stop each service.
echo.
