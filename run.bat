@echo off
cd %~dp0
call .venv\scripts\activate.bat
python bot_v2c.py
pause
