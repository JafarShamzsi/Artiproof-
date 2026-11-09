@echo off
setlocal enabledelayedexpansion
title ArtiProof - Research Integrity Platform
color 0A

:: ================================================================
::  ArtiProof Local Development Startup Script (Windows)
::  Usage:
::    start.bat              - Full startup (Docker + Backend + Frontend)
::    start.bat setup        - First-time setup only (install deps, push schema)
::    start.bat backend      - Start backend only (assumes Docker is running)
::    start.bat frontend     - Start frontend only
::    start.bat docker       - Start Docker services only
::    start.bat seed         - Seed demo data
::    start.bat stop         - Stop all services
::    start.bat status       - Check service status
:: ================================================================

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"

if "%1"=="stop" goto :stop
if "%1"=="status" goto :status
if "%1"=="seed" goto :seed
if "%1"=="setup" goto :setup
if "%1"=="docker" goto :docker_only
if "%1"=="backend" goto :backend_only
if "%1"=="frontend" goto :frontend_only

:: ── Full startup ──
echo.
echo  ============================================
echo   ArtiProof - Research Integrity Platform
echo  ============================================
echo.

:: Check prerequisites
call :check_prereqs
if errorlevel 1 goto :eof

:: Start Docker services
call :start_docker
if errorlevel 1 goto :eof

:: Wait for PostgreSQL
call :wait_for_postgres
if errorlevel 1 goto :eof

:: Push database schema
call :push_schema

:: Start backend
call :start_backend

:: Start frontend
call :start_frontend

echo.
echo  ============================================
echo   All services started!
echo  ============================================
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo   To seed demo data, run:
echo     start.bat seed
echo.
echo   To stop everything:
echo     start.bat stop
echo  ============================================
echo.
goto :eof

:: ================================================================
::  SUBROUTINES
:: ================================================================

:check_prereqs
echo  [1/6] Checking prerequisites...

where docker >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Docker not found. Install Docker Desktop.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Docker Desktop is not running. Please start it.
    exit /b 1
)
echo         Docker ............. OK

where python >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.12+.
    exit /b 1
)
echo         Python ............. OK

where node >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Node.js not found. Install Node.js 18+.
    exit /b 1
)
echo         Node.js ............ OK

where npm >nul 2>&1
if errorlevel 1 (
    echo  ERROR: npm not found. Install Node.js.
    exit /b 1
)
echo         npm ................ OK
echo.
exit /b 0

:start_docker
echo  [2/6] Starting Docker services (PostgreSQL + Redis)...
cd /d "%ROOT%"
docker compose up -d postgres redis >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Failed to start Docker services.
    exit /b 1
)
echo         PostgreSQL ......... started (port 5432)
echo         Redis .............. started (port 6379)
echo.
exit /b 0

:wait_for_postgres
echo  [3/6] Waiting for PostgreSQL to be ready...
set retries=0
:pg_loop
if %retries% geq 30 (
    echo  ERROR: PostgreSQL did not become ready after 30 seconds.
    exit /b 1
)
docker exec artiproof-postgres pg_isready -U artiproof -q >nul 2>&1
if errorlevel 1 (
    set /a retries+=1
    timeout /t 1 /nobreak >nul
    goto :pg_loop
)
echo         PostgreSQL ready after %retries%s
echo.
exit /b 0

:push_schema
echo  [4/6] Pushing database schema via Prisma...
cd /d "%FRONTEND_DIR%"

:: Install frontend deps if needed
if not exist "node_modules" (
    echo         Installing frontend dependencies...
    call npm install --silent 2>nul
)

:: Generate Prisma client and push schema
call npx prisma generate --no-hints >nul 2>&1
call npx prisma db push --accept-data-loss 2>nul
if errorlevel 1 (
    echo         First-time setup detected, resetting database schema...
    call npx prisma db push --force-reset 2>nul
    if errorlevel 1 (
        echo  WARNING: Prisma db push failed. Run 'npx prisma db push --force-reset' manually in frontend/.
    ) else (
        echo         Database schema created (fresh)
    )
) else (
    echo         Database schema in sync
)
echo.
exit /b 0

:start_backend
echo  [5/6] Starting backend (FastAPI on port 8000)...
cd /d "%BACKEND_DIR%"

:: Create venv if it doesn't exist
if not exist "venv" (
    echo         Creating Python virtual environment...
    python -m venv venv
)

:: Install dependencies
echo         Installing backend dependencies...
call venv\Scripts\pip install -q -r requirements.txt 2>nul

:: Start backend in background
start "" /min "%BACKEND_DIR%\run-dev.bat"
echo         Backend starting on http://localhost:8000
echo.
exit /b 0

:start_frontend
echo  [6/6] Starting frontend (Next.js on port 3000)...
cd /d "%FRONTEND_DIR%"

:: Install deps if needed
if not exist "node_modules" (
    echo         Installing frontend dependencies...
    call npm install --silent 2>nul
)

:: Start frontend in background
start "" /min "%FRONTEND_DIR%\run-dev.bat"
echo         Frontend starting on http://localhost:3000
echo.
exit /b 0

:: ================================================================
::  COMMANDS
:: ================================================================

:setup
echo.
echo  ArtiProof - First-Time Setup
echo  ===============================
echo.

call :check_prereqs
if errorlevel 1 goto :eof

:: Start Docker
call :start_docker
call :wait_for_postgres

:: Backend setup
echo  Setting up backend...
cd /d "%BACKEND_DIR%"
if not exist "venv" (
    python -m venv venv
    echo         Virtual environment created
)
call venv\Scripts\pip install -q -r requirements.txt
echo         Backend dependencies installed

:: Frontend setup
echo  Setting up frontend...
cd /d "%FRONTEND_DIR%"
call npm install --silent 2>nul
echo         Frontend dependencies installed

:: Push schema
call :push_schema

:: Generate Prisma client
cd /d "%FRONTEND_DIR%"
call npx prisma generate --no-hints >nul 2>&1
echo         Prisma client generated

echo.
echo  Setup complete! Run 'start.bat' to start all services.
echo.
goto :eof

:docker_only
echo  Starting Docker services...
cd /d "%ROOT%"
docker compose up -d postgres redis
echo  Done. PostgreSQL on 5432, Redis on 6379.
goto :eof

:backend_only
echo  Starting backend...
cd /d "%BACKEND_DIR%"
if not exist "venv" (
    echo  ERROR: Run 'start.bat setup' first.
    goto :eof
)
call venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
goto :eof

:frontend_only
echo  Starting frontend...
cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo  ERROR: Run 'start.bat setup' first.
    goto :eof
)
call npm run dev
goto :eof

:seed
echo.
echo  Seeding demo data...
echo.
curl -s -X POST http://localhost:8000/api/seed/demo
echo.
echo.
echo  Demo data seeded! Visit http://localhost:3000
echo.
goto :eof

:stop
echo.
echo  Stopping all ArtiProof services...
echo.

:: Kill processes on ports 8000 and 3000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /pid %%a /f >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    taskkill /pid %%a /f >nul 2>&1
)

:: Stop Docker services
cd /d "%ROOT%"
docker compose stop >nul 2>&1

echo  All services stopped.
echo.
goto :eof

:status
echo.
echo  ArtiProof Service Status
echo  ==========================
echo.

:: Check Docker
docker compose ps 2>nul
echo.

:: Check backend
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo  Backend:   STOPPED
) else (
    echo  Backend:   RUNNING (http://localhost:8000)
)

:: Check frontend
curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    echo  Frontend:  STOPPED
) else (
    echo  Frontend:  RUNNING (http://localhost:3000)
)
echo.
goto :eof
