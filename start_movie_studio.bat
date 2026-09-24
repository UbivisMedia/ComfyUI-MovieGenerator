@echo off
cd /d "%~dp0"

if "%~1"=="" goto MENU

echo ====================================================
echo STARTING MOVIEGENERATOR - MASTER DIRECTOR [CLI MODE]
echo Screenplay: %~nx1
echo ====================================================
echo.
python master_regisseur.py "%~1"
echo.
pause
exit /b

:MENU
cls
echo ====================================================
echo             MOVIEGENERATOR - MOVIE STUDIO
echo ====================================================
echo.
echo  [1] Launch Movie Studio (Web GUI) [Default]
echo  [2] Launch Master Director (Terminal CLI)
echo  [3] Exit
echo.
echo ====================================================
set "choice="
set /p "choice=Select an option [1-3] (Default: 1): "
if "%choice%"=="" set choice=1

if "%choice%"=="1" goto START_GUI
if "%choice%"=="2" goto START_CLI
if "%choice%"=="3" exit /b

echo Invalid selection. Please choose 1, 2, or 3.
timeout /t 2 >nul
goto MENU

:START_GUI
echo.
echo Starting Movie Studio Web GUI...
python movie_studio.py
echo.
pause
exit /b

:START_CLI
echo.
echo Starting Master Director Terminal CLI...
python master_regisseur.py
echo.
pause
exit /b
