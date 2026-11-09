@echo off
setlocal EnableDelayedExpansion

:: ArtiProof - Development Run Script (Windows)
:: Usage: run.bat [start|stop|restart|seed|status]

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"

if "%~1"=="" goto start
if /i "%~1"=="start" goto start
if /i "%~1"=="stop" goto stop
if /i "%~1"=="restart" goto restart
if /i "%~1"=="seed" goto seed
if /i "%~1"=="status" goto status
echo Usage: run.bat [start^|stop^|restart^|seed^|status]
exit /b 1

:: ========== START ==========
:start
echo.
echo ========================================
echo    ArtiProof - Development Server
echo ========================================
echo.

call :start_docker
call :start_backend
call :start_frontend

echo.
echo ========================================
echo    All services are running!
echo ========================================
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo   Demo Login:
echo     Email:    demo@artiproof.com
echo     Password: demo1234
echo.
echo   Close this window or press Ctrl+C to stop.
echo.

:: Keep window open - wait for frontend process
if defined FRONTEND_PID (
    echo Waiting for services... Press Ctrl+C to stop.
    pause >nul
)
goto :eof

:: ========== STOP ==========
:stop
echo [ArtiProof] Stopping services...

:: Kill uvicorn (backend)
taskkill /F /IM uvicorn.exe >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Backend stopped
) else (
    echo [--] Backend was not running
)

:: Kill node (frontend) - be specific to avoid killing unrelated node processes
for /f "tokens=2" %%a in ('wmic process where "commandline like '%%next dev%%'" get processid /value 2^>nul ^| findstr ProcessId') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo [OK] Frontend stopped

:: Stop Docker containers
docker-compose -f "%PROJECT_DIR%\docker-compose.yml" stop postgres redis >nul 2>&1
echo [OK] Docker services stopped
echo.
goto :eof

:: ========== RESTART ==========
:restart
call :stop
timeout /t 2 /nobreak >nul
call :start
goto :eof

:: ========== SEED ==========
:seed
echo [ArtiProof] Seeding database...
curl -s -X POST http://localhost:8000/api/seed/demo
echo.
echo [OK] Database seeded
goto :eof

:: ========== STATUS ==========
:status
echo.
echo === ArtiProof Status ===
echo.

curl -s http://localhost:8000/health >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK]    Backend:    http://localhost:8000
) else (
    echo [DOWN]  Backend:    NOT RUNNING
)

curl -s http://localhost:3000 >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK]    Frontend:   http://localhost:3000
) else (
    echo [DOWN]  Frontend:   NOT RUNNING
)

docker exec artiproof-postgres pg_isready -U artiproof -d artiproof >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK]    PostgreSQL: localhost:5432
) else (
    echo [DOWN]  PostgreSQL: NOT RUNNING
)

docker exec artiproof-redis redis-cli ping >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK]    Redis:      localhost:6379
) else (
    echo [DOWN]  Redis:      NOT RUNNING
)

echo.
echo Demo Login:
echo   Email:    demo@artiproof.com
echo   Password: demo1234
echo.
goto :eof

:: ========== HELPERS ==========

:start_docker
echo [ArtiProof] Starting Docker services (PostgreSQL + Redis)...
docker-compose -f "%PROJECT_DIR%\docker-compose.yml" up -d postgres redis

echo [ArtiProof] Waiting for services to be healthy...
set "RETRIES=0"
:docker_wait_loop
if !RETRIES! geq 30 (
    echo [WARN] Timed out waiting for PostgreSQL
    goto docker_wait_done
)
docker exec artiproof-postgres pg_isready -U artiproof -d artiproof >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] PostgreSQL is ready
    goto docker_wait_done
)
set /a RETRIES+=1
timeout /t 1 /nobreak >nul
goto docker_wait_loop
:docker_wait_done

docker exec artiproof-redis redis-cli ping >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Redis is ready
)
goto :eof

:start_backend
echo [ArtiProof] Starting backend (FastAPI on :8000)...

:: Start backend in a new minimized window
start "ArtiProof-Backend" /min cmd /c "cd /d "%BACKEND_DIR%" && call venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait for backend to be ready
set "RETRIES=0"
:backend_wait_loop
if !RETRIES! geq 15 (
    echo [WARN] Backend may still be starting...
    goto backend_wait_done
)
timeout /t 1 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Backend running at http://localhost:8000
    goto backend_wait_done
)
set /a RETRIES+=1
goto backend_wait_loop
:backend_wait_done
goto :eof

:start_frontend
echo [ArtiProof] Starting frontend (Next.js on :3000)...

:: Start frontend in a new minimized window
start "ArtiProof-Frontend" /min cmd /c "cd /d "%FRONTEND_DIR%" && npm run dev"

:: Wait for frontend to be ready
set "RETRIES=0"
:frontend_wait_loop
if !RETRIES! geq 20 (
    echo [WARN] Frontend may still be starting...
    goto frontend_wait_done
)
timeout /t 1 /nobreak >nul
curl -s http://localhost:3000 >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Frontend running at http://localhost:3000
    goto frontend_wait_done
)
set /a RETRIES+=1
goto frontend_wait_loop
:frontend_wait_done
goto :eof
