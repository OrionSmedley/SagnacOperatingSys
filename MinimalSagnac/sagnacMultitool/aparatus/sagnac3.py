# User instructions: import the myHF2LI and magnet objects for the sagnac interferometer





# patch the old packages calling visa
# this is a hack to make the old packages work with pyvisa

#############################################################################################################################
import pyvisa

# Simulate the `visa` module as an alias for `pyvisa`
import sys

# Create a fake 'visa' module, which is essentially an alias for pyvisa
sys.modules['visa'] = pyvisa

# Optionally, map all attributes from pyvisa to visa (this is technically unnecessary because the alias works)
for attr in dir(pyvisa):
    setattr(sys.modules['visa'], attr, getattr(pyvisa, attr))

#############################################################################################################################


from pymeasure.instruments.keithley import Keithley2400
keith = Keithley2400("GPIB::24")


from pymeasure.instruments.attocube import APS100
mag = APS100('COM4')