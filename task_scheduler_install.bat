@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM Determine project root (batch located at repo root)
set SCRIPT_DIR=%~dp0
set PYTHON_EXEC=python
set REPORT_SCRIPT="%SCRIPT_DIR%report_builder.py"

if not exist %REPORT_SCRIPT% (
    echo [Scheduler] report_builder.py not found at %REPORT_SCRIPT%
    exit /b 1
)

echo [Scheduler] Registering Outlook AutoReport daily task...
schtasks /Create ^
    /TN "OutlookAutoReportDaily" ^
    /TR "%PYTHON_EXEC% %REPORT_SCRIPT%" ^
    /SC DAILY ^
    /ST 07:00 ^
    /RL HIGHEST ^
    /F

if %ERRORLEVEL% NEQ 0 (
    echo [Scheduler] Failed to register task. Run in elevated command prompt.
    exit /b %ERRORLEVEL%
)

echo [Scheduler] Task registered successfully.
endlocal
