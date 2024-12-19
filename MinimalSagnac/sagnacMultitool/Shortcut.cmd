@echo off
call code "%~1"
echo Your File is "%~1"

call conda activate pipPymeasMod
cd /d "%~dp0"

:: Ask user what they want to do
set /p choice=Enter your choice - [p]lot, [r]un, [a]ll: 


:: Run the appropriate script
if "%choice%"=="p" (
    python plotter.py "%~1"  
)

if "%choice%"=="r" (
    python experimenter.py "%~1"
)

if "%choice%"=="a" (
    start /b python plotter.py "%~1"  
    :: Runs plotter.py in the background
    python experimenter.py "%~1" 
)

cmd /k

