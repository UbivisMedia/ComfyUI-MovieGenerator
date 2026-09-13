@echo off
cd /d "%~dp0"

echo ====================================================
echo STARTING AI MOVIE GENERATOR / KI-STUDIO
if "%~1"=="" (
    echo Mode: Interactive selection from Projects folder
) else (
    echo Loading screenplay: %~nx1
)
echo ====================================================
echo.

python master_regisseur.py %1

echo.
pause