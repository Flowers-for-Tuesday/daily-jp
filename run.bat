@echo off
echo Starting daily Japanese learning pipeline...

REM === 1. Run vocab/main.py ===
echo.
echo Running vocab...
python "%~dp0vocab\main.py"

REM === 2. Run read/main.py ===
echo.
echo Running reading module...
python "%~dp0read\main.py"

REM === 3. Run listen/main.py ===
echo.
echo Running listening module...
python "%~dp0listen\main.py"

REM === 4. Run listen/sender.py ===
echo.
echo Sending email...
python "%~dp0listen\sender.py"

echo.
echo All tasks completed.
pause
