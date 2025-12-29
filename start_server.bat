@echo off
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py" --server --port 9000 --no-signals --no-banner --verbose
