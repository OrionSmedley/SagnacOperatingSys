@echo off
call code "%~1"
echo Your File is "%~1"

call conda activate pipPymeasMod
cd /d "%~dp0"


echo Hit any key to plot
set /p choice=
start /b python plotter.py "%~1"


echo Hit any key to run
set /p choice=
python experimenter.py "%~1"


cmd /k

