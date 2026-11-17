@echo off
setlocal
set "PYTHONW=C:\Program Files\Python314\pythonw.exe"
if not exist "%PYTHONW%" (
    echo Python was not found at "%PYTHONW%".
    pause
    exit /b 1
)
start "" "%PYTHONW%" "%~dp0sistertwin_worker.py"
exit /b 0
