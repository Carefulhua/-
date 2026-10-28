@echo off
chcp 65001 >nul
pushd "%~dp0"

echo ========================================
echo   Invoice Renamer + Excel
echo ========================================
echo.

set PYTHON=
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe" set PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe
if not defined PYTHON set PYTHON=python

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install from https://www.python.org/
    pause
    exit /b 1
)

echo Step 1: Rename invoices...
if exist invoice-renamer.exe (
    invoice-renamer.exe .
) else (
    "%PYTHON%" invoice-renamer.py .
)
echo.

echo Step 2: Generate Excel summary...
"%PYTHON%" invoice-to-excel.py .
echo.

echo All done!
popd >nul 2>&1
pause
