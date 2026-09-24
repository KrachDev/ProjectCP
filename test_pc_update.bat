@echo off
setlocal enabledelayedexpansion
title ChromeGrid Quick Updater - Test PC Receiver

echo ========================================================
echo       ChromeGrid Test PC Auto-Updater
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

set DL_FILE=%TEMP%\ChromeGrid_Update_%RANDOM%.zip
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
tar -tf "!DL_FILE!" 2>nul | findstr /i "content.js" >nul
if %errorlevel%==0 set IS_EXT=1

if "!IS_EXT!"=="1" (
    echo [*] Detected Chrome Extension Update.
    echo [*] Extracting to C:\ChromeGridExtension...
    if not exist "C:\ChromeGridExtension" mkdir "C:\ChromeGridExtension"
    tar -xf "!DL_FILE!" -C "C:\ChromeGridExtension" >nul 2>&1
    if not !errorlevel!==0 (
        powershell -NoProfile -Command "Expand-Archive -Path '!DL_FILE!' -DestinationPath 'C:\ChromeGridExtension' -Force"
    )

    :: Dispatch instant zero-click reload command to running ChromeGridLauncher (if active)
    curl.exe -s http://127.0.0.1:8765/reload_extension >nul 2>&1

    echo.
    echo ========================================================
    echo   [SUCCESS] C:\ChromeGridExtension updated!
    echo.
    echo   ACTIVATION (Do ONE of the following):
    echo   1. If ChromeGridLauncher is running, reload command was sent!
    echo   2. Or in Chrome, go to chrome://extensions and click 
    echo      the reload button (circular arrow) on "Chrome Grid Sync Bridge"
    echo   3. Or restart Chrome from ChromeGridLauncher.
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
