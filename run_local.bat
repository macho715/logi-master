@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%

echo [RunLocal] Activating inbox reader (dry run)...
python -m inbox_reader --dry-run --verbose
if %ERRORLEVEL% NEQ 0 goto :error

echo [RunLocal] Generating sample report...
python -m report_builder --sample --verbose
if %ERRORLEVEL% NEQ 0 goto :error

echo [RunLocal] Outputs located in work/
goto :eof

:error
echo [RunLocal] Command failed with exit code %ERRORLEVEL%
exit /b %ERRORLEVEL%

:eof
endlocal
