@echo off
setlocal enabledelayedexpansion
title ChromeGrid Quick Updater - Send to Test PC

echo ========================================================
echo       ChromeGrid Fast Update Sender (Dev -> Test PC)
echo ========================================================
echo.
echo Select what you want to send:
echo   [1] Extension only (content.js & background.js) - ~60 KB [INSTANT: 1 sec]
echo   [2] Full Launcher Package (ChromeGridLauncher_Package.zip) - ~60 MB
echo.

set /p CHOICE="Enter choice [1 or 2, default is 1]: "
if "%CHOICE%"=="" set CHOICE=1

if "%CHOICE%"=="2" goto SEND_PACKAGE
if "%CHOICE%"=="1" goto SEND_EXTENSION

echo Invalid choice. Defaulting to Extension.
goto SEND_EXTENSION

:SEND_EXTENSION
echo.
echo [*] Syncing latest extension files (v1.3.1)...
if not exist "%~dp0publish\ChromeGridExtension" mkdir "%~dp0publish\ChromeGridExtension"
copy /y "%~dp0ChromeGridLauncher\ChromeGridExtension\manifest.json" "%~dp0publish\ChromeGridExtension\manifest.json" >nul
copy /y "%~dp0ChromeGridLauncher\ChromeGridExtension\background.js" "%~dp0publish\ChromeGridExtension\background.js" >nul
copy /y "%~dp0ChromeGridLauncher\ChromeGridExtension\content.js" "%~dp0publish\ChromeGridExtension\content.js" >nul

:: Also copy to local C:\ChromeGridExtension if it exists
if exist "C:\ChromeGridExtension" (
    copy /y "%~dp0ChromeGridLauncher\ChromeGridExtension\manifest.json" "C:\ChromeGridExtension\manifest.json" >nul
    copy /y "%~dp0ChromeGridLauncher\ChromeGridExtension\background.js" "C:\ChromeGridExtension\background.js" >nul
    copy /y "%~dp0ChromeGridLauncher\ChromeGridExtension\content.js" "C:\ChromeGridExtension\content.js" >nul
)

set ZIP_FILE=%~dp0publish\ChromeGridExtension_Update.zip
if exist "!ZIP_FILE!" del /f /q "!ZIP_FILE!" >nul 2>&1

:: Pack clean extension files directly into root of ZIP
pushd "%~dp0publish\ChromeGridExtension"
tar -a -c -f "!ZIP_FILE!" manifest.json background.js content.js >nul 2>&1
popd

if not exist "!ZIP_FILE!" (
    :: Fallback to powershell zip if tar isn't present
    powershell -NoProfile -Command "Compress-Archive -Path '%~dp0publish\ChromeGridExtension\manifest.json', '%~dp0publish\ChromeGridExtension\background.js', '%~dp0publish\ChromeGridExtension\content.js' -DestinationPath '!ZIP_FILE!' -Force" >nul 2>&1
)

if not exist "!ZIP_FILE!" (
    echo [ERROR] Failed to create extension zip file.
    pause
    exit /b 1
)

set UPLOAD_TARGET=!ZIP_FILE!
goto DO_UPLOAD

:SEND_PACKAGE
echo.
set ZIP_FILE=%~dp0publish\ChromeGridLauncher_Package.zip
if not exist "!ZIP_FILE!" (
    echo [*] Packaging full release...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scratch\compress_package.ps1"
)

if not exist "!ZIP_FILE!" (
    echo [ERROR] Package zip not found at: !ZIP_FILE!
    pause
    exit /b 1
)

set UPLOAD_TARGET=!ZIP_FILE!
goto DO_UPLOAD

:DO_UPLOAD
echo [*] Uploading to high-speed transfer server...
set RESP_FILE=%TEMP%\cgl_upload_%RANDOM%.json

curl.exe -s -F "file=@!UPLOAD_TARGET!" https://tmpfiles.org/api/v1/upload > "%RESP_FILE%"

if not exist "%RESP_FILE%" (
    echo [ERROR] Upload failed or no connection.
    pause
    exit /b 1
)

:: Extract URL from JSON response
set RAW_URL=
for /f "tokens=2 delims=:,}" %%A in ('type "%RESP_FILE%" ^| findstr "https://tmpfiles.org/"') do (
    set "RAW_URL=%%~A"
)

:: Trim quotes and clean url
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

:: Form direct download link (by inserting /dl/ right after tmpfiles.org/)
set "DL_URL=!RAW_URL:https://tmpfiles.org/=https://tmpfiles.org/dl/!"

del /f /q "%RESP_FILE%" >nul 2>&1

:: Copy link to Windows clipboard
echo !DL_URL!| clip.exe

echo.
echo ========================================================
echo   [SUCCESS] Link ready and COPIED TO YOUR CLIPBOARD!
echo ========================================================
echo.
echo  Download Link:
echo  !DL_URL!
echo.
echo  Web Page Link:
echo  !RAW_URL!
echo.
echo  Paste (Ctrl+V) this link on your test PC to download!
echo ========================================================
echo.
pause
