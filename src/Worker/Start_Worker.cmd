@echo off
setlocal
"C:\Program Files\Python314\python.exe" -u "%~dp0sistertwin_worker.py"
set "RESULT=%ERRORLEVEL%"
echo Worker stopped. Exit code: %RESULT%
pause
exit /b %RESULT%
