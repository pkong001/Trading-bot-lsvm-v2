@echo off
cd %~dp0
call .venv\scripts\activate.bat
python main.py
pause
