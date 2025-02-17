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
import time
session = Session("localhost", hf2=True)
myHF2LI = session.connect_device("DEV1004")

# set timeconstants for all channels
def setTc(Tc): 
    [myHF2LI.demods[demod].timeconstant(Tc) for demod in range(6)]
    myHF2LI.Tc = Tc
myHF2LI.setTc = setTc

def waitTc(n): 
    """Wait for n time constants"""
    print(f"Waiting for {n}Tc =  ({n*myHF2LI.Tc} s)")
    time.sleep(n*myHF2LI.Tc)
myHF2LI.waitTc = waitTc

# get value of a demodulator
def dem(demod): return myHF2LI.demods[demod].sample()
myHF2LI.dem = dem





from pymeasure.instruments.newport import ESP300
from pymeasure.adapters import DAQmxAdapter


delayStage = ESP300(11)




    

def singleLockin():
    import time
    from moku.instruments import LockInAmp

    i = LockInAmp('[fe80::32e2:83ff:fea0:7141%2]', force_connect=True)
    i.set_frontend(1, coupling='AC', impedance='1MOhm',
                    attenuation='-20dB')
    i.set_frontend(2, coupling='AC', impedance='1MOhm',
                    attenuation='-20dB')


    i.set_demodulation('ExternalPLL', frequency=3.347620e6, phase=160)
    i.set_filter(15.6, slope='Slope6dB')
    i.set_gain(1,1)


    i.set_outputs('X',"Y")
    # i.set_aux_output(3.347620e6, 0.65) # How do I set this to "demodulation"


    i.set_monitor(1, 'Demod')
    i.set_monitor(2, 'Input1')
    i.set_monitor(3, 'MainOutput')
    i.set_monitor(4, 'AuxOutput')


    # Do I really need this? for data streaming?
    i.set_trigger(type='Edge', source='ProbeA', level=0)
    i.set_timebase(-1e-6, 1e-6)


    def sample():
        sample.df = pd.DataFrame(i.get_data())
        return True
    i.sample = sample

    return i


from types import MethodType
def SidebandDemod(f_eom = 3.347620e6, f_i = 3.27320e3, Tc = 0.01):
    """ returns a multiinstrument object
    f_eom is the frequency of the EOM, 
    f_i is the frequency of the current for sideband
    """

    fc = 1/(2*np.pi*Tc) # corner frequency


## Multi Instrument
    import time
    from moku.instruments import MultiInstrument
    from moku.instruments import WaveformGenerator, LockInAmp

    m = MultiInstrument('[fe80::5871:e09a:a71e:c8cf%8]', platform_id=4, force_connect=True)
    wg = m.set_instrument(1, WaveformGenerator)
    har2 = m.set_instrument(2, LockInAmp)
    har1 = m.set_instrument(3, LockInAmp)
    sideband = m.set_instrument(4, LockInAmp)

    connections = [ # Inputs
        dict(source="Input1", destination="Slot2InA"),
        dict(source="Input1", destination="Slot3InA"),
        dict(source="Input1", destination="Slot4InA"),
        # dict(source="Slot3OutA", destination="Slot4InA"), ## Tandem Demod

        # signal Generation if use PLL
        dict(source="Slot1OutA", destination="Slot2InB"),
        dict(source="Slot1OutA", destination="Slot3InB"),
        dict(source="Slot1OutB", destination="Slot4InB"),
        # Outputs
        dict(source="Slot1OutA", destination="Output1"),
        dict(source="Slot1OutB", destination="Output2")]
    print(m.set_connections(connections=connections))


    m.set_frontend(1, coupling='AC', impedance='1MOhm', attenuation='-20dB')
    # m.set_frontend(2, coupling='AC', impedance='1MOhm', attenuation='-20dB')
    m.set_output(1, "0dB")
    m.set_output(2, "14dB")

## wave generator
    wg.generate_waveform(channel=1, type="Sine",
                         frequency=f_eom, amplitude=0.65, 
                         offset=0, phase=0)   
    wg.generate_waveform(channel=2, type="Sine",
                         frequency=f_i, amplitude=2, 
                         offset=0, phase=0)  


## Harmonic 2
    har2.set_demodulation('Internal', frequency=f_eom*2, phase=0)
    har2.set_gain(0,0)


## Harmonic 1
    har1.set_demodulation('Internal', frequency=f_eom, phase=0)
    har1.set_gain(70,70)


## Sideband
    sideband.set_demodulation('Internal', frequency=f_eom-f_i, phase=0)
    sideband.set_gain(110,110)

## All Lockins
    for instru in [har2, har1, sideband]:

        instru.set_filter(fc, slope='Slope6dB')  # Tc = 10ms
        instru.set_outputs('X',"Y")
        instru.set_monitor(1, 'MainOutput')
        instru.set_monitor(2, 'AuxOutput')
        # for get_data, not for data streaming
        instru.set_trigger(mode='Auto', type='Edge', source='ProbeA', level=0)
        instru.set_timebase(-1e-6, 1e-6)

        instru.set_acquisition_mode(mode="Precision")

    m.sync()


## Exporting Data:
    def sample(self):
        tic = time.time()
        self.df = pd.DataFrame(self.get_data(wait_complete=True))
        toc = time.time()
        print(f"{self.__class__.__name__} ({id(self)}): runtime {tic - toc}")
    har2.sample = MethodType(sample, har2)
    har1.sample = MethodType(sample, har1)
    sideband.sample = MethodType(sample, sideband)

    def sample_all(self):
        for instru in [har2, har1, sideband]:
            instru.sample()
    m.sample = MethodType(sample_all, m)

    def setTc(self, Tc):
        fc = 1/(2*np.pi*Tc) # corner frequency
        m.Tc = Tc
        for instru in [har2, har1, sideband]:
            instru.set_filter(fc)
    m.setTc = MethodType(setTc, m)
    m.setTc(Tc)

    def waitTc(self, n):
        """Wait for n time constants"""
        print(f"Waiting for {n}Tc =  ({n*self.Tc} s)")
        time.sleep(n*self.Tc)
    m.waitTc = MethodType(waitTc, m)

    return m, wg, har2, har1, sideband



######################################################
#############################################################################################################################
#############################################################################################################################
#############################################################################################################################
# END OF IMPORTS!!!
#############################################################################################################################
#############################################################################################################################
#############################################################################################################################


defaults = {"myHF2LI.setTc": 0.1}

