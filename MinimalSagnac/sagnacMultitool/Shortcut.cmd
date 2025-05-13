@echo off
call code "%~1"
echo Your File is "%~1"

call conda activate pipPymeasMod
cd /d "%~dp0"



start /b python plotter.py "%~1"



echo ______________________________
echo Hit any key to run
echo ______________________________
echo .
echo .
set /p choice=
python experimenter.py "%~1"


cmd /k

