@echo off
echo Building ChromeGridLauncher.exe...
python -m PyInstaller --noconfirm ChromeGridLauncher.spec
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo Build successful! Executable is located at:
    echo dist\ChromeGridLauncher.exe
    echo ========================================================
) else (
    echo.
    echo [ERROR] Build failed.
)
pause
