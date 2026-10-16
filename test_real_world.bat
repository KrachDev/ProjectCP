@echo off
setlocal enabledelayedexpansion
title Phylakon - Safe Real-World Testing Protocol

echo ========================================================
echo    [+] PHYLAKON: SAFE REAL-WORLD TEST LAUNCHER
echo ========================================================
echo.
echo [*] Safety Guards Enabled:
echo     - Auto-Submit: DISABLED (Prevents 24h Lockout)
echo     - Auto-Reload: DISABLED (No rapid request loops)
echo     - Dwell Time: 15s Minimum
echo     - Profile: Isolated Test Profile (Protects personal data)
echo.

set "SRC_DIR=C:\Users\krach\Documents\BLS Project\Phylakon"
set "EXT_DIR=C:\PhylakonExtension"

if exist "!SRC_DIR!\manifest.json" (
    robocopy "!SRC_DIR!" "!EXT_DIR!" manifest.json /NFL /NDL /NJH /NJS /nc /ns >nul 2>&1
    for %%D in (background content icons modules popup rules loaded) do (
        robocopy "!SRC_DIR!\%%D" "!EXT_DIR!\%%D" /E /NFL /NDL /NJH /NJS /nc /ns >nul 2>&1
    )
)

if not exist "!EXT_DIR!\manifest.json" set "EXT_DIR=C:\Phylakon"
if not exist "!EXT_DIR!\manifest.json" set "EXT_DIR=C:\Users\krach\Documents\BLS Project\Phylakon"

set "USER_DATA_DIR=%TEMP%\Phylakon_Chrome_Test_Profile"
set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"

if not exist "!CHROME_EXE!" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "!CHROME_EXE!" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if not exist "!CHROME_EXE!" (
    echo [ERROR] Google Chrome not found at standard paths.
    pause
    exit /b 1
)

echo [*] Starting Phylakon Companion Controller in background...
start "" python "%~dp0phylakon_controller.py"

echo [*] Launching Chrome in Safe Real-World Inspection Mode...
echo [*] Loading Pure Extension from: !EXT_DIR!
start "" "!CHROME_EXE!" ^
    --user-data-dir="!USER_DATA_DIR!" ^
    --load-extension="!EXT_DIR!" ^
    --disable-background-timer-throttling ^
    --disable-backgrounding-occluded-windows ^
    "https://www.blsspainmorocco.net/"

echo.
echo ========================================================
echo [SUCCESS] Chrome launched with Pure Phylakon Extension!
echo.
echo Real-World Checklist to observe:
echo 1. Check top-right HUD: Verify "Phylakon Active (Safe Mode)"
echo 2. Check DevTools (F12) Console: Observe [SessionTracker] output
echo 3. Check Companion Controller: Verify Session Countdown badge appears
echo 4. Paste passport/details: Verify paste and right-click work
echo 5. Open Date Picker: Verify calendar stays pinned and does not collapse
echo ========================================================
echo.
timeout /t 5 >nul
