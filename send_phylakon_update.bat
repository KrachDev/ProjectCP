@echo off
setlocal enabledelayedexpansion
title Phylakon Quick Updater - Send to Test PC

echo ========================================================
echo       [+] PHYLAKON EXTENSION FAST UPDATE SENDER
echo ========================================================
echo.

set "SRC_DIR=C:\Users\krach\Documents\BLS Project\Phylakon"
set "PHYLAKON_DIR=C:\PhylakonExtension"

if exist "!SRC_DIR!\manifest.json" (
    robocopy "!SRC_DIR!" "!PHYLAKON_DIR!" manifest.json /NFL /NDL /NJH /NJS /nc /ns >nul 2>&1
    for %%D in (background content icons modules popup rules loaded) do (
        robocopy "!SRC_DIR!\%%D" "!PHYLAKON_DIR!\%%D" /E /NFL /NDL /NJH /NJS /nc /ns >nul 2>&1
    )
)

if not exist "!PHYLAKON_DIR!\manifest.json" set "PHYLAKON_DIR=C:\Phylakon"
if not exist "!PHYLAKON_DIR!\manifest.json" set "PHYLAKON_DIR=C:\Users\krach\Documents\BLS Project\Phylakon"

echo [*] Packing Pure Extension from: !PHYLAKON_DIR!

set "ZIP_FILE=%~dp0publish\Phylakon_Extension_Update.zip"
if not exist "%~dp0publish" mkdir "%~dp0publish"
if exist "!ZIP_FILE!" del /f /q "!ZIP_FILE!" >nul 2>&1

pushd "!PHYLAKON_DIR!"
tar -a -c -f "!ZIP_FILE!" manifest.json background content icons modules popup rules loaded 2>nul
popd

if not exist "!ZIP_FILE!" (
    powershell -NoProfile -Command "Compress-Archive -Path '!PHYLAKON_DIR!\manifest.json', '!PHYLAKON_DIR!\background', '!PHYLAKON_DIR!\content', '!PHYLAKON_DIR!\icons', '!PHYLAKON_DIR!\modules', '!PHYLAKON_DIR!\popup', '!PHYLAKON_DIR!\rules', '!PHYLAKON_DIR!\loaded' -DestinationPath '!ZIP_FILE!' -Force"
)

if not exist "!ZIP_FILE!" (
    echo [ERROR] Failed to create extension zip file.
    pause
    exit /b 1
)

echo [*] Uploading to high-speed transfer server...
set RESP_FILE=%TEMP%\phylakon_upload_%RANDOM%.json

curl.exe -s -F "file=@!ZIP_FILE!" https://tmpfiles.org/api/v1/upload > "%RESP_FILE%"

if not exist "%RESP_FILE%" (
    echo [ERROR] Upload failed or no connection.
    pause
    exit /b 1
)

set RAW_URL=
for /f "tokens=2 delims=:,}" %%A in ('type "%RESP_FILE%" ^| findstr "https://tmpfiles.org/"') do (
    set "RAW_URL=%%~A"
)

set RAW_URL=!RAW_URL:"=!
set RAW_URL=!RAW_URL:\/=//!
set RAW_URL=!RAW_URL: =!

if "!RAW_URL!"=="" (
    echo [ERROR] Could not parse upload URL from response:
    type "%RESP_FILE%"
    del /f /q "%RESP_FILE%" >nul 2>&1
    pause
    exit /b 1
)

set "DL_URL=!RAW_URL:https://tmpfiles.org/=https://tmpfiles.org/dl/!"
del /f /q "%RESP_FILE%" >nul 2>&1

echo !DL_URL!| clip.exe

echo.
echo ========================================================
echo   [+] [SUCCESS] Pure Phylakon Extension Ready and COPIED TO CLIPBOARD!
echo ========================================================
echo.
echo  Direct Download Link:
echo  !DL_URL!
echo.
echo  Paste (Ctrl+V) this link on your test PC receiver (test_pc_update.bat)!
echo ========================================================
echo.
pause
