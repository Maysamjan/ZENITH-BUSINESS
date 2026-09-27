@echo off
rem ============================================================================
rem  Zenith Business - reset the test data back to the original sample database.
rem
rem  This deletes your current test "appdata" folder and restores the pristine
rem  seeded copy that shipped with this build (appdata_seed). Use it whenever you
rem  want to start the acceptance test again from a clean, known state.
rem
rem  No Python or internet connection is required.
rem ============================================================================
setlocal
echo.
echo  This will DELETE your current test data and restore the original
echo  sample database. Any receipts/payments/expenses you posted while
echo  testing will be removed.
echo.
choice /m "Reset the test data now"
if errorlevel 2 goto :cancel

echo Restoring pristine sample database...
if exist "%~dp0appdata" rmdir /s /q "%~dp0appdata"
xcopy "%~dp0appdata_seed" "%~dp0appdata\" /e /i /q /y >nul
echo Done. You can start the app again with Run-ZenithBusiness.bat.
goto :end

:cancel
echo Cancelled. Nothing was changed.

:end
echo.
pause
endlocal
