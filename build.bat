@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo           EyeDash - Build
echo ========================================
echo.

echo [1/3] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [2/3] Installing/updating PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: Could not install PyInstaller.
    pause
    exit /b 1
)

echo.
echo [3/3] Building EyeDash.exe...
python -m PyInstaller --clean --noconfirm EyeDash.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build successful!
echo ========================================
echo Executable: %CD%\dist\EyeDash.exe
echo.
pause
endlocal
