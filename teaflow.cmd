@echo off
setlocal
set "TEAFLOW_NODE=%~dp0.tools\node\node.exe"
if not exist "%TEAFLOW_NODE%" (
    echo The local Node runtime is missing. See START_HERE.md.
    exit /b 1
)
pushd "%~dp0web\backend"
if errorlevel 1 exit /b 1
if /I "%~1"=="setup" goto setup
if /I "%~1"=="test" goto test
if /I "%~1"=="iot" goto iot
if /I "%~1"=="serve" goto serve
if /I "%~1"=="mouse" goto mouse
if "%~1"=="" goto serve
echo Usage: teaflow.cmd [serve^|setup^|test^|iot^|mouse]
set "TEAFLOW_EXIT=1"
goto done
:serve
"%TEAFLOW_NODE%" src\server.js
goto result
:setup
"%TEAFLOW_NODE%" scripts\setup.js
goto result
:test
"%TEAFLOW_NODE%" --test --test-concurrency=1 test\*.test.js
goto result
:iot
"%~dp0.tools\python\python.exe" "%~dp0iot\api\app.py"
goto result
:mouse
call "%~dp0cashier-mouse.cmd"
:result
set "TEAFLOW_EXIT=%ERRORLEVEL%"
:done
popd
exit /b %TEAFLOW_EXIT%
