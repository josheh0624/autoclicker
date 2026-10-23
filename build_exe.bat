@echo off
cd /d "%~dp0"
echo ========================================================
echo Building standalone AutoClicker.exe with PyInstaller...
echo ========================================================

python -m PyInstaller --noconsole --onefile --collect-all customtkinter --name "AutoClicker" autoclicker.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo Build successful! Executable is located in dist\AutoClicker.exe
    echo Copying AutoClicker.exe to current folder for easy access...
    copy /y "dist\AutoClicker.exe" "AutoClicker.exe" >nul
    echo Done!
    echo ========================================================
) else (
    echo.
    echo Build failed. Check the errors above.
)
pause

