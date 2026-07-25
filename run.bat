@echo off
REM ============================================================================
REM  run.bat - MOD-SA Dev Launcher
REM  Starts backend (FastAPI/uvicorn) and frontend (Vite/React) dev servers
REM  each in their own titled terminal window, after verifying dependencies.
REM ============================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

REM --- Get a real ESC char for ANSI color codes -------------------------------
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "C_INFO=%ESC%[36m"
set "C_OK=%ESC%[32m"
set "C_WARN=%ESC%[33m"
set "C_ERR=%ESC%[31m"
set "C_BOLD=%ESC%[1m"
set "C_RESET=%ESC%[0m"

REM Enable ANSI processing in this console (no-op if already on / unsupported).
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

call :banner

set "FAILED=0"
set "SUM_COUNT=0"

REM --- Check 1: Python on PATH -------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    call :err "Python not found on PATH."
    call :hint "Install Python 3.10+ from https://www.python.org/downloads/ and re-run."
    call :fail_summary "Python interpreter" "MISSING"
) else (
    call :ok "Python found on PATH."
    call :pass_summary "Python interpreter" "OK"
)

REM --- Check 2: Node.js + npm on PATH ------------------------------------------
where node >nul 2>&1
if errorlevel 1 (
    call :err "Node.js not found on PATH."
    call :hint "Install Node.js LTS from https://nodejs.org/ and re-run."
    call :fail_summary "Node.js runtime" "MISSING"
) else (
    call :ok "Node.js found on PATH."
    call :pass_summary "Node.js runtime" "OK"
)

where npm >nul 2>&1
if errorlevel 1 (
    call :err "npm not found on PATH."
    call :hint "npm ships with Node.js - reinstall Node.js from https://nodejs.org/."
    call :fail_summary "npm" "MISSING"
) else (
    call :ok "npm found on PATH."
    call :pass_summary "npm" "OK"
)

REM --- Check 3: Backend virtual environment ------------------------------------
set "VENV_ACTIVATE="
if exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%BACKEND_DIR%\.venv\Scripts\activate.bat"
) else if exist "%BACKEND_DIR%\venv\Scripts\activate.bat" (
    set "VENV_ACTIVATE=%BACKEND_DIR%\venv\Scripts\activate.bat"
)

if not defined VENV_ACTIVATE (
    call :err "No backend virtual environment found (looked for backend\.venv and backend\venv)."
    call :hint "Create one with:"
    call :hint "    cd backend"
    call :hint "    python -m venv .venv"
    call :hint "    .venv\Scripts\activate"
    call :hint "    pip install -r requirements.txt"
    call :fail_summary "Backend virtual environment" "MISSING"
) else (
    call :ok "Backend virtual environment found: !VENV_ACTIVATE!"
    call :pass_summary "Backend virtual environment" "OK"
)

REM --- Check 4: backend requirements.txt (advisory only) -----------------------
if exist "%BACKEND_DIR%\requirements.txt" (
    call :ok "backend\requirements.txt found."
    call :pass_summary "Backend requirements.txt" "OK"
) else (
    call :warn "backend\requirements.txt not found - skipping dependency file check."
    call :pass_summary "Backend requirements.txt" "WARN"
)

REM --- Check 5: backend .env (auto-copy from .env.example if missing) ---------
if exist "%BACKEND_DIR%\.env" (
    call :ok "backend\.env found."
    call :pass_summary "Backend .env config" "OK"
) else (
    if exist "%BACKEND_DIR%\.env.example" (
        call :warn "backend\.env not found - copying from backend\.env.example."
        copy /Y "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
        call :ok "Created backend\.env from .env.example."
        call :pass_summary "Backend .env config" "CREATED"
    ) else (
        call :err "backend\.env is missing and no backend\.env.example exists to copy from."
        call :hint "Create backend\.env manually with the required settings (see backend\README.md)."
        call :fail_summary "Backend .env config" "MISSING"
    )
)

REM --- Check 6: frontend package.json ------------------------------------------
if exist "%FRONTEND_DIR%\package.json" (
    call :ok "frontend\package.json found."
    call :pass_summary "Frontend package.json" "OK"
) else (
    call :err "frontend\package.json not found."
    call :hint "The frontend project appears to be missing under: %FRONTEND_DIR%"
    call :fail_summary "Frontend package.json" "MISSING"
)

REM --- Check 7: frontend node_modules ------------------------------------------
if exist "%FRONTEND_DIR%\node_modules" (
    call :ok "frontend\node_modules found."
    call :pass_summary "Frontend dependencies (node_modules)" "OK"
) else (
    call :err "frontend\node_modules not found - dependencies are not installed."
    call :hint "Install them with:"
    call :hint "    cd frontend"
    call :hint "    npm install"
    call :fail_summary "Frontend dependencies (node_modules)" "MISSING"
)

REM --- Print summary -------------------------------------------------------------
call :print_summary

if "%FAILED%"=="1" (
    echo.
    echo %C_ERR%%C_BOLD%Startup aborted: one or more required dependencies are missing.%C_RESET%
    echo %C_ERR%See the [ERROR] messages above for exact fix-it commands.%C_RESET%
    echo.
    endlocal
    exit /b 1
)

REM --- Launch backend (background, output streams into this same console) ---
echo.
call :info "Starting backend server in background (output streams below)..."
start "" /B cmd /c "cd /d "%BACKEND_DIR%" && call "%VENV_ACTIVATE%" && uvicorn main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%"

REM Brief pause so backend startup lines print before frontend lines mix in.
timeout /t 2 /nobreak >nul

REM --- Launch frontend (foreground - keeps this window/console alive) --------
echo.
echo %C_OK%%C_BOLD%Both services are starting in this single console.%C_RESET%
echo   %C_BOLD%Backend Server%C_RESET%  : http://127.0.0.1:%BACKEND_PORT%   (health check: http://127.0.0.1:%BACKEND_PORT%/health)
echo   %C_BOLD%Frontend Dev Server%C_RESET% : http://localhost:%FRONTEND_PORT%
echo.
echo %C_INFO%Backend and frontend output will interleave below. Press Ctrl+C to stop%C_RESET%
echo %C_INFO%the frontend; the backend keeps running until this console is closed.%C_RESET%
echo.

call :info "Starting frontend dev server (foreground)..."
pushd "%FRONTEND_DIR%"
call npm run dev
popd

REM --- Cleanup: frontend stopped (e.g. Ctrl+C) - stop the background backend --
echo.
call :info "Frontend stopped. Shutting down background backend (uvicorn)..."
REM Find the PID listening on the backend port and kill it (and children).
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /T /F >nul 2>&1
)
call :ok "Done."

endlocal
exit /b 0

REM ============================================================================
REM  Subroutines
REM ============================================================================

:banner
echo.
echo %C_BOLD%%C_INFO%============================================================%C_RESET%
echo %C_BOLD%%C_INFO%              MOD-SA Dev Launcher                            %C_RESET%
echo %C_BOLD%%C_INFO%   KMUTT Student Affairs RAG Chatbot - Backend + Frontend   %C_RESET%
echo %C_BOLD%%C_INFO%============================================================%C_RESET%
echo Checking dependencies...
echo.
exit /b

:info
echo %C_INFO%[INFO]%C_RESET% %~1
exit /b

:ok
echo %C_OK%[OK]%C_RESET% %~1
exit /b

:warn
echo %C_WARN%[WARN]%C_RESET% %~1
exit /b

:err
echo %C_ERR%[ERROR]%C_RESET% %~1
exit /b

:hint
echo %C_ERR%        %~1%C_RESET%
exit /b

:fail_summary
set /a SUM_COUNT+=1
set "SUM!SUM_COUNT!=  %C_ERR%[%~2]%C_RESET% %~1"
set "FAILED=1"
exit /b

:pass_summary
set /a SUM_COUNT+=1
if "%~2"=="WARN" (
    set "SUM!SUM_COUNT!=  %C_WARN%[%~2]%C_RESET% %~1"
) else (
    set "SUM!SUM_COUNT!=  %C_OK%[%~2]%C_RESET% %~1"
)
exit /b

:print_summary
echo.
echo %C_BOLD%------------------------- Dependency Summary -------------------------%C_RESET%
for /L %%i in (1,1,%SUM_COUNT%) do (
    call echo %%SUM%%i%%
)
echo %C_BOLD%-----------------------------------------------------------------------%C_RESET%
exit /b
