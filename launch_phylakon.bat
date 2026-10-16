@echo off
setlocal enabledelayedexpansion
title Phylakon: Legend Reborn - Master Controller Launcher

echo ========================================================
echo    ⚡ PHYLAKON: LEGEND REBORN - COMPANION CONTROLLER
echo ========================================================
echo.
echo [*] Checking environment...

set PY_EXE=
where python >nul 2>&1
if %errorlevel%==0 (
    set PY_EXE=python
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set PY_EXE=py
    )
)

if not "!PY_EXE!"=="" (
    echo [*] Starting Phylakon Controller via Python...
    start "" !PY_EXE! "%~dp0phylakon_controller.py"
    goto FINISH
)

:: If python is not on PATH, check if compiled ChromeGridLauncher.exe exists
if exist "%~dp0dist\ChromeGridLauncher.exe" (
    echo [*] Python not in PATH. Starting compiled ChromeGridLauncher.exe (with Phylakon integrated)...
    start "" "%~dp0dist\ChromeGridLauncher.exe"
    goto FINISH
)

if exist "%~dp0publish\ChromeGridLauncher.exe" (
    echo [*] Python not in PATH. Starting publish\ChromeGridLauncher.exe (with Phylakon integrated)...
    start "" "%~dp0publish\ChromeGridLauncher.exe"
    goto FINISH
)

echo [ERROR] Neither Python nor ChromeGridLauncher.exe was found.
echo Please install Python (3.9+) or compile ChromeGridLauncher via build.bat.
pause
exit /b 1

:FINISH
echo.
echo [SUCCESS] Phylakon Companion Controller launched!
timeout /t 3 >nul
exit /b 0
