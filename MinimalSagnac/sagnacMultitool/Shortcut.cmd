:: Initialize environment
call conda activate pipPymeasMod
cd /d "%~dp0"

:: Ask user what they want to d
echo Your File is "%~1"
set /p choice=Enter your choice - [v]iew, [p]lot, [r]un, [a]ll: 




:: Run the appropriate script
if "%choice%"=="v" (
    code "%~1"
) else if "%choice%"=="p" (
     start /b python plotter.py "%~1"  
     :: Runs plotter.py in the background
) else if "%choice%"=="r" (
    python experimenter.py "%~1"
) else if "%choice%"=="a" (
    start /b python plotter.py "%~1"  
    :: Runs plotter.py in the background
    python experimenter.py "%~1"     
    :: Runs experimenter.py after plotter.py starts
) else (
    echo Invalid choice. Exiting.
)

cmd /k
