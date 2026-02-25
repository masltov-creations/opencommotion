@echo off
setlocal
set "ROOT=%~dp0"
set "CLI=%ROOT%scripts\opencommotion.py"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py "%CLI%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%CLI%" %*
  exit /b %ERRORLEVEL%
)

echo Python is required to run OpenCommotion.
exit /b 1
