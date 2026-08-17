@echo off
rem ============================================================================
rem  Zenith Business - Stage 05 Owner Test Build (portable launcher)
rem
rem  Double-click this file to start the application.
rem
rem  It points the app at the PORTABLE "appdata" folder that ships next to it,
rem  which already contains the fresh test database with sample data. Nothing is
rem  installed on your PC and nothing outside this folder is touched. To start
rem  over with clean sample data at any time, run Reset-Test-Data.bat.
rem ============================================================================
setlocal
set "ZENITH_DATA_HOME=%~dp0appdata"
start "" "%~dp0app\ZenithBusiness.exe"
endlocal
