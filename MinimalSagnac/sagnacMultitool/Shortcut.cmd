@echo off
call code "%~1"
echo Your File is "%~1"

call conda activate pipPymeasMod
cd /d "%~dp0"


set /p choice= [P]lot? (default no)
if "%choice%"=="p" (
    start python plotter.py "%~1"  
)

set /p choice= [r]un? (default no)
if "%choice%"=="r" (
    python experimenter.py "%~1"
)

cmd /k

