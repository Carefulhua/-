@echo off
chcp 65001 >nul
pushd "%~dp0"
echo Current dir: %CD%
echo.

REM --- Find Python ---
set PYTHON=
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe
if not defined PYTHON set PYTHON=python

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found.
    pause
    exit /b 1
)
"%PYTHON%" --version
echo.

REM --- Install deps ---
"%PYTHON%" -m pip install pypdf pyinstaller openpyxl --quiet
if errorlevel 1 (
    echo pip install failed.
    pause
    exit /b 1
)
echo Dependencies ready.
echo.

REM --- Clean old builds ---
if exist build rmdir /s /q build 2>nul
if exist dist rmdir /s /q dist 2>nul
if exist invoice-renamer.spec del /q invoice-renamer.spec 2>nul

REM --- Build EXE directly ---
echo Building invoice-renamer.exe ...
"%PYTHON%" -m PyInstaller --onefile --collect-all pypdf --name invoice-renamer --distpath . invoice-renamer.py
if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

if exist invoice-renamer.exe (
    echo.
    echo ========================================
    echo Build successful!
    echo EXE: invoice-renamer.exe
    echo ========================================
) else (
    echo.
    echo Build failed - invoice-renamer.exe not found.
)

popd
pause
