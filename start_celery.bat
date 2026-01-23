@echo off
REM ============================================================================
REM GreenSIG Celery Worker + Beat Startup Script
REM ============================================================================
REM
REM This script starts the Celery worker with Beat scheduler for:
REM - Background task processing (exports, notifications)
REM - Periodic tasks (distribution status updates, cleanup)
REM
REM Prerequisites:
REM - Redis must be running: docker-compose up redis -d
REM - Virtual environment must exist: .venv\
REM - Dependencies installed: pip install -r requirements.txt
REM
REM ============================================================================

echo ============================================
echo  GreenSIG - Celery Worker + Beat
echo ============================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate

REM Check if celery is installed
python -c "import celery" 2>nul
if errorlevel 1 (
    echo ERROR: Celery not installed!
    echo Please run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo Starting Celery worker with Beat scheduler...
echo.
echo Press Ctrl+C to stop.
echo.

REM Start Celery with:
REM   --pool=solo      : Required for Windows (no multiprocessing)
REM   --beat           : Enable periodic task scheduler
REM   --scheduler      : Use Django database scheduler for Beat
REM   --loglevel=info  : Show info level logs
celery -A greensig_web worker --beat --loglevel=info --pool=solo --scheduler django_celery_beat.schedulers:DatabaseScheduler

pause
