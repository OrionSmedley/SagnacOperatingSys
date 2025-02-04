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




# Make the sagnac warning flags show up in the notebook
import logging

# Configure logging to output to the notebook's cell
logging.basicConfig(level=logging.WARNING,  # Log only WARNING or above by default
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])





# MAGNET CONTROL
from .drivers.custom_instruments1 import daedalusProjField
from pymeasure.adapters import DAQmxAdapter

calib_file = 'C:\\Users\\Ralph Group\\Documents\\Github\\SagnacOperatingSys\\sagnac_control\\calibrations\\sagnac'

magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
magnet.load_calibration_params(calib_file)

# magnet.set_vector_field(
#     B=0,
#     phi=0, 
#     theta=0)




#imports for Zurich Instruments
import os
import numpy as np
import pandas as pd
from zhinst.toolkit import Session
session = Session("localhost", hf2=True)
myHF2LI = session.connect_device("DEV1004")

# set timeconstants for all channels
def setTc(Tc): [myHF2LI.demods[demod].timeconstant(Tc) for demod in range(6)]
myHF2LI.setTc = setTc

# get value of a demodulator
def dem(demod): return myHF2LI.demods[demod].sample()
myHF2LI.dem = dem





from pymeasure.instruments.newport import ESP300
from pymeasure.adapters import DAQmxAdapter


delayStage = ESP300(11)


######################################################
#############################################################################################################################
#############################################################################################################################
#############################################################################################################################
# END OF IMPORTS!!!
#############################################################################################################################
#############################################################################################################################
#############################################################################################################################


defaults = {"myHF2LI.setTc": 0.1}

