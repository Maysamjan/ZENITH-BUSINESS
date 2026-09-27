@echo off
rem ============================================================================
rem  Zenith Business - build the Windows test package ON A WINDOWS MACHINE.
rem
rem  Requirements:
rem    * Windows 10/11 (64-bit)
rem    * Python 3.11+ installed and on PATH  (https://www.python.org/downloads/)
rem
rem  What it does (no changes to any Stage 01-05 functionality):
rem    1. creates a throwaway virtual environment
rem    2. installs the app + PyInstaller
rem    3. freezes the app into a standalone ZenithBusiness.exe (no Python needed
rem       to RUN afterwards)
rem    4. seeds a fresh test database with sample data
rem    5. assembles a portable, double-click-to-run package under  dist\package
rem
rem  Run it from the repository root:
rem      packaging\build_windows.bat
rem ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0.."
set "ROOT=%CD%"
set "PKG=%ROOT%\dist\package"

echo.
echo === [1/5] Creating build virtual environment ===
python -m venv .buildvenv || goto :fail
call .buildvenv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip >nul

echo.
echo === [2/5] Installing application + PyInstaller ===
pip install -e . || goto :fail
pip install pyinstaller || goto :fail

echo.
echo === [3/5] Freezing ZenithBusiness.exe ===
pyinstaller packaging\zenith_business.spec --noconfirm --clean || goto :fail

echo.
echo === [4/5] Assembling portable package ===
if exist "%PKG%" rmdir /s /q "%PKG%"
mkdir "%PKG%"
xcopy "%ROOT%\dist\ZenithBusiness" "%PKG%\app\" /e /i /q /y >nul
copy /y "%ROOT%\packaging\Run-ZenithBusiness.bat" "%PKG%\" >nul
copy /y "%ROOT%\packaging\Reset-Test-Data.bat" "%PKG%\" >nul
copy /y "%ROOT%\packaging\READ-ME-FIRST.md" "%PKG%\READ-ME-FIRST.txt" >nul

echo Seeding fresh sample database...
python packaging\seed_test_db.py "%PKG%\appdata" || goto :fail
xcopy "%PKG%\appdata" "%PKG%\appdata_seed\" /e /i /q /y >nul

echo.
echo === [5/5] Done ===
echo Portable test package is ready at:
echo     %PKG%
echo Double-click  %PKG%\Run-ZenithBusiness.bat  to test.
call deactivate
endlocal
exit /b 0

:fail
echo.
echo BUILD FAILED. See the messages above.
call deactivate 2>nul
endlocal
exit /b 1
