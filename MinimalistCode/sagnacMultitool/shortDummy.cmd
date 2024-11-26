call conda activate pipPymeasMod  
:: Activates the `pipPymeasMod` Conda environment

cd /d "%~dp0"  
:: Changes to the directory where this script is located (`%~dp0`), including changing drives if needed

python experimenter.py "%~1"  
:: Runs `experimenter.py` with the first argument passed to this script (`%~1`)

cmd /k  
:: Keeps the Command Prompt open after execution to view output or errors
