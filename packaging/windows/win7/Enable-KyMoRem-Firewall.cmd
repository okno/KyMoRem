@echo off
setlocal
cd /d "%~dp0"

set "EXE="
set "ARCH=%PROCESSOR_ARCHITECTURE%"
if /I "%PROCESSOR_ARCHITEW6432%"=="AMD64" set "ARCH=AMD64"

if /I "%ARCH%"=="AMD64" (
  if exist "%~dp0KyMoRem-0.2.0-rc1-windows7-x64-client.exe" set "EXE=%~dp0KyMoRem-0.2.0-rc1-windows7-x64-client.exe"
)
if not defined EXE (
  if exist "%~dp0KyMoRem-0.2.0-rc1-windows7-x86-client.exe" set "EXE=%~dp0KyMoRem-0.2.0-rc1-windows7-x86-client.exe"
)
if not defined EXE (
  echo KyMoRem Win7 client executable not found in:
  echo %~dp0
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process -FilePath '%EXE%' -ArgumentList '--install-firewall-rules' -Verb RunAs -Wait"

if errorlevel 1 (
  echo Firewall rule setup did not complete.
  pause
  exit /b 1
)

echo KyMoRem firewall rules requested for private LAN access.
pause
