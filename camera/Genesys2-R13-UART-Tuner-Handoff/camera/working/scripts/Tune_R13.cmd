@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tune_r13.ps1" %*
if errorlevel 1 pause
