@echo off
call code "%~1"
echo Your File is "%~1"

call conda activate pipPymeasMod
cd /d "%~dp0"


set /p choice= Hit any key to plot
start /b python plotter.py "%~1"

set /p choice= Hit any key to run
python experimenter.py "%~1"


cmd /k

