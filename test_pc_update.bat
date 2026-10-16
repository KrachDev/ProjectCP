@echo off
setlocal enabledelayedexpansion
title Universal Quick Updater - Test PC Receiver

echo ========================================================
echo       Pure Extension Receiver (C:\PhylakonExtension)
echo ========================================================
echo.

set URL=%1
if "!URL!"=="" (
    set /p URL="Paste the download URL: "
)

if "!URL!"=="" (
    echo [ERROR] No URL provided.
    pause
    exit /b 1
)

:: Ensure URL uses direct download /dl/ if from tmpfiles.org
echo !URL! | findstr /i "tmpfiles.org" >nul
if %errorlevel%==0 (
    echo !URL! | findstr /i "tmpfiles.org/dl/" >nul
    if not !errorlevel!==0 (
        set "URL=!URL:https://tmpfiles.org/=https://tmpfiles.org/dl/!"
    )
)

set DL_FILE=%TEMP%\Universal_Update_%RANDOM%.zip
echo.
echo [*] Downloading update from: !URL!
curl.exe -s -L "!URL!" -o "!DL_FILE!"

if not exist "!DL_FILE!" (
    echo [ERROR] Download failed. Check your internet connection or the link.
    pause
    exit /b 1
)

echo [*] Download complete! Checking package contents...

:: Detect if this is an extension update or full package
set IS_EXT=0
tar -tf "!DL_FILE!" 2>nul | findstr /i "manifest.json" >nul
if %errorlevel%==0 set IS_EXT=1

if "!IS_EXT!"=="1" (
    echo [*] Detected Chrome Extension Update.
    echo [*] Extracting to pure extension root: C:\PhylakonExtension ...
    if not exist "C:\PhylakonExtension" mkdir "C:\PhylakonExtension"
    tar -xf "!DL_FILE!" -C "C:\PhylakonExtension" >nul 2>&1
    if not !errorlevel!==0 (
        powershell -NoProfile -Command "Expand-Archive -Path '!DL_FILE!' -DestinationPath 'C:\PhylakonExtension' -Force"
    )

    :: Keep C:\Phylakon and C:\ChromeGridExtension synchronized
    if not exist "C:\Phylakon" (
        cmd /c 'mklink /J "C:\Phylakon" "C:\PhylakonExtension"' >nul 2>&1
    )
    if exist "C:\ChromeGridExtension" (
        tar -xf "!DL_FILE!" -C "C:\ChromeGridExtension" >nul 2>&1
    )

    :: Dispatch instant zero-click reload command to running server / controller (if active)
    curl.exe -s http://127.0.0.1:8765/reload_extension >nul 2>&1

    echo.
    echo ========================================================
    echo   [SUCCESS] C:\PhylakonExtension updated!
    echo.
    echo   ACTIVATION:
    echo   1. In Chrome (chrome://extensions), click the reload 
    echo      button on "Phylakon - Legend Reborn".
    echo   2. Or relaunch via test_real_world.bat.
    echo ========================================================
) else (
    echo [*] Detected Full Package / Launcher Update.
    echo Extract to current folder? [Y/N]
    set /p CONFIRM="Enter choice [Y]: "
    if "!CONFIRM!"=="" set CONFIRM=Y
    if /i "!CONFIRM!"=="Y" (
        tar -xf "!DL_FILE!" >nul 2>&1
        if not !errorlevel!==0 (
            powershell -NoProfile -Command "Expand-Archive -Path '!DL_FILE!' -DestinationPath '.' -Force"
        )
        echo.
        echo ========================================================
        echo   [SUCCESS] Package extracted into current folder!
        echo ========================================================
    )
)

del /f /q "!DL_FILE!" >nul 2>&1
echo.
pause
