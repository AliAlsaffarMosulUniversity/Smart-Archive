@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run build_windows.bat first, or install requirements in a Python environment.
 pause
 exit /b 1
)
.venv\Scripts\python app.py
pause
