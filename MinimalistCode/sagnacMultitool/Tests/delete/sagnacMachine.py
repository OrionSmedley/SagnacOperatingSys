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
from aparatus.drivers.custom_instruments import daedalusProjField
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



import time


#############################################################################################################################
#############################################################################################################################
#############################################################################################################################
# END OF IMPORTS!!!
# BEGINNING OF FUNCTION DEFINITIONS
#############################################################################################################################
#############################################################################################################################
#############################################################################################################################


def perform_measurement(saveFile):
    print("performing measurement \n")

    data = {}
    dat = [myHF2LI.demods[demod].sample() for demod in range(6)]
    J2J1 = 0.543
    J1J0 = 1.837
    deg2rad = np.pi/180.

    bx, by, bz = magnet.get_cart_vector_field()


    data.update({
        "mag/B": magnet.getField(),
        "mag/phi": magnet.getPhi(),
        "mag/theta": magnet.getTheta(),
        "mag/Bx": bx,
        "mag/By": by,
        "mag/Bz": bz,
        "Time": dat[0]['timestamp'],
        "ThetaK": np.arctan(J2J1 * dat[3]['x'] / dat[2]['y']) / 2,
        "X1": dat[3]['x'],
        "Y1": dat[3]['y'],
        "X2": dat[2]['x'],
        "Y2": dat[2]['y'],
        "DeltaThetaK": J2J1 * dat[4]['x'] / dat[2]['y'],
        "DeltaThetaK_DualSideband": J2J1 * (dat[4]['x'] + dat[5]['x']) / 2 / dat[2]['y'],
        "DeltaX1_C-M": dat[4]['x'],
        "DeltaY1_C-M": dat[4]['y'],
        "DeltaX1_C+M": dat[5]['x'],
        "DeltaY1_C+M": dat[5]['y'],
        "TX1": dat[0]['x'],
        "TY1": dat[0]['y'],
        "TX2": dat[1]['x'],
        "TY2": dat[1]['y']
    })

    df = pd.DataFrame(data, index=[0])
    df.to_csv(saveFile, mode='a', header=not os.path.exists(saveFile), index=False)


def set_parameter(**kwargs):
    print("setting parameters on the apparatus.")
    for name, value in kwargs.items():
        # Strip off the part after an underscore
        base_name = name.split('_')[0]
        print(f"\tSetting {base_name} to {value}")

        if base_name == 'B':
            magnet.setField(value)
            while magnet.in_motion:
                pass

        elif base_name == 'phi':
            magnet.setPhi(value)
            while magnet.in_motion:
                pass
            
        elif base_name == 'theta':
            magnet.setTheta(value)
            while magnet.in_motion:
                pass

        elif base_name == "Tc":
            for demod in range(6):
                myHF2LI.demods[demod].timeconstant(value)


        elif base_name == 'wait':
            time.sleep(value)

        else:
            print(f"Unknown parameter {base_name}, from {name}")
