@echo off
cd %~dp0
call vbot2\scripts\activate.bat
python bot_v2c.py
pause
