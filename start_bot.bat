@echo off
rem Start LINE bot + cloudflared tunnel + set webhook. Close this window (or Ctrl+C) to stop.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python bot.py up
pause
