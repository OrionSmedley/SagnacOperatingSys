:: Ask user what they want to do
@echo off
echo Your File is "%~1"
set /p choice=Enter your choice - [v]iew, [p]lot, [r]un, [a]ll: 


:: Run the appropriate script




if "%choice%"=="v" (
    code "%~1"  
)

if "%choice%"=="p" (
    call conda activate pipPymeasMod
    cd /d "%~dp0"

    python plotter.py "%~1"  
)

if "%choice%"=="r" (
    call conda activate pipPymeasMod
    cd /d "%~dp0"

    python experimenter.py "%~1"
)

if "%choice%"=="a" (
    call conda activate pipPymeasMod
    cd /d "%~dp0"

    start /b python plotter.py "%~1"  
    :: Runs plotter.py in the background
    python experimenter.py "%~1" 
)

cmd /k

