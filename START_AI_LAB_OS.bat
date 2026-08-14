@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py "%~dp0launcher.py"
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0launcher.py"
    exit /b %errorlevel%
)

echo.
echo [AI LAB OS] Python was not found.
echo Install Python or add it to PATH, then run this file again.
echo.
pause
exit /b 1
