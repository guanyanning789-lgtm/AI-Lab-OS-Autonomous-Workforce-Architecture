@echo off
setlocal
set "AI_LAB_ROOT=%~dp0"
python "%AI_LAB_ROOT%scripts\ai_lab.py" --repo "%AI_LAB_ROOT%." %*
exit /b %ERRORLEVEL%
