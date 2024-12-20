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


# Make the sagnac warning flags show up in the notebook
import logging

# Configure logging to output to the notebook's cell
logging.basicConfig(level=logging.WARNING,  # Log only WARNING or above by default
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

#############################################################################################################################
#############################################################################################################################





try: # Zurich Instruments
    import os
    import numpy as np
    import pandas as pd
    from zhinst.toolkit import Session
    session = Session("localhost", hf2=True)
    myHF2LI = session.connect_device("DEV18338")

    # set timeconstants for all channels
    def setTc(Tc): [myHF2LI.demods[demod].timeconstant(Tc) for demod in range(6)]
    myHF2LI.setTc = setTc

    # get value of a demodulator
    def dem(demod): return myHF2LI.demods[demod].sample()
    myHF2LI.dem = dem

    # def get_vout(self, out_num, osc_num):
    #     return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num))
    # def set_vout(self, out_num, osc_num, x):
    #     self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/amplitudes/' + str(osc_num), x)
    # myHF2LI.get_vout = get_vout
    # myHF2LI.get_vout = set_vout

    from types import MethodType

    # Define the new methods
    def get_vout(self, out_num, osc_num):
        return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num))

    def set_vout(self, out_num, osc_num, x):
        self.setDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num), x)

    # Bind the methods to the instance `myHF2LI`
    myHF2LI.get_vout = MethodType(get_vout, myHF2LI)
    myHF2LI.set_vout = MethodType(set_vout, myHF2LI)






    # from pymeasure.instruments.zurich import HF2LI
    # pyHF2LI(8005, 1, 18338)
except:
    print("sagnac3.0: no Zurich")



try: # Magnet
    from pymeasure.instruments.attocube import APS100
    mag = APS100('COM4')
except:
    print("sagnac3.0: no magnet aps100")



try: # Keithly
    from pymeasure.instruments.keithley import Keithley2400
    keith = Keithley2400("GPIB::26")
except:
    print( "sagnac3.0: no keith")



try: # Owon osciloscope
    import vds1022 as owon
    vds = owon.VDS1022(debug=0)
    vds.set_channel(owon.CH1, range='10v', probe='x1')
    # usage: vds.fetch().ch1.rms()
except:
    print("sagnac3.0: no owon")