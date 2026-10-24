@echo off
setlocal
set "TEAFLOW_MOUSE_PYTHON=%~dp0.tools\python\python.exe"
"%TEAFLOW_MOUSE_PYTHON%" -c "import tkinter" >nul 2>&1
if errorlevel 1 set "TEAFLOW_MOUSE_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%TEAFLOW_MOUSE_PYTHON%" (
    echo Mouse control needs Python with Tk support. See iot\tools\MOUSE_CONTROL.md.
    exit /b 1
)
"%TEAFLOW_MOUSE_PYTHON%" "%~dp0iot\tools\cashier_mouse.py" %*
exit /b %ERRORLEVEL%
