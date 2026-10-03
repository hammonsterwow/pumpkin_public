@echo off
setlocal
cd /d "%~dp0"

echo Pumpkin customer app launcher
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_customer_mobile.ps1"
set "PUMPKIN_EXIT=%ERRORLEVEL%"

if not "%PUMPKIN_EXIT%"=="0" (
  echo.
  echo Customer app startup failed. Review the message above.
  pause
)

exit /b %PUMPKIN_EXIT%
