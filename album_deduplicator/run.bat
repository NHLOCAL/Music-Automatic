@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

python scripts\check_dependencies.py
if errorlevel 1 (
    echo.
    echo Dependency check failed. Fix the missing dependencies above and run again.
    exit /b 1
)

cd frontend
npm run dev:electron
