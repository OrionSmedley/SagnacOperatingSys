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

    def dc(v=None):
        Vrange = myHF2LI.sigouts[1].range()
        if v is not None:
            myHF2LI.sigouts[1].offset(v / Vrange)
        return myHF2LI.sigouts[1].offset() * Vrange

    def ac(v=None):
        Vrange = myHF2LI.sigouts[1].range()
        if v is not None:
            myHF2LI.sigouts[1].amplitudes[7-1](v / Vrange)
        return myHF2LI.sigouts[1].amplitudes[7-1]() * Vrange
    myHF2LI.dc = dc
    myHF2LI.ac = ac




    # def get_vout(self, out_num, osc_num):
    #     return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num))
    # def set_vout(self, out_num, osc_num, x):
    #     self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/amplitudes/' + str(osc_num), x)
    # myHF2LI.get_vout = get_vout
    # myHF2LI.get_vout = set_vout

    # from types import MethodType

    # # Define the new methods
    # def get_vout(self, out_num, osc_num):
    #     return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num))

    # def set_vout(self, out_num, osc_num, x):
    #     self.setDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num), x)

    # # Bind the methods to the instance `myHF2LI`
    # myHF2LI.get_vout = MethodType(get_vout, myHF2LI)
    # myHF2LI.set_vout = MethodType(set_vout, myHF2LI)






    # from pymeasure.instruments.zurich import HF2LI
    # pyHF2LI(8005, 1, 18338)
except:
    print("sagnac3.0: no Zurich")



try: # Magnet

    import sys
    module_dir = r"D:\Github\SagnacOperatingSys\VecMagSagnac_control"
    sys.path.append(module_dir)
    from sagnac.custom_instruments import vectorMagnetFullUSB
    mag = vectorMagnetFullUSB()
    import atto_device.CRYO2100 as cr
    atto = cr("192.168.1.1")
    atto.connect()
#     mag.setSafeWaitBx = lambda b: mag.setSafe_wait_cart(b,mag.By_set,mag.Bz_set)
#     mag.setSafeWaitBy = lambda b: mag.setSafe_wait_cart(mag.Bx_set,b,mag.Bz_set)
#     mag.setSafeWaitBz = lambda b: mag.setSafe_wait_cart(mag.Bx_set,mag.By_set,b)

#     ## usage: mag.setSafeWaitBx(0.04)




# #+Bx is 0deg azimuthal, +By is 90deg azimuthal (90deg polar), -Bx is 180deg azimuthal, -By is 270deg azimuthal, +Bz is 0deg polar
#     mag.setSafeWaitB = lambda b: mag.setSafe_wait_polar(b,mag.phi_set,mag.theta_set)
#     mag.setSafeWaitPhi = lambda phi: mag.setSafe_wait_polar(mag.B_set,phi,mag.theta_set)
#     mag.setSafeWaitTheta = lambda theta: mag.setSafe_wait_polar(mag.B_set,mag.phi_set,theta)

except:
    print("sagnac3.0: no magnet aps100")








try: # Magnet High Z

    import sys
    module_dir = r"D:\Github\SagnacOperatingSys\VecMagSagnac_control"
    sys.path.append(module_dir)
    from sagnac.custom_instruments import vectorMagnetFullUSB_highZ
    mag_highZ = vectorMagnetFullUSB_highZ()
    # mag_highZ.connect_highZ()


    import atto_device.CRYO2100 as cr
    atto = cr("192.168.1.1")
    atto.connect()

    import time

    Tthresh = 4.2
    ATOL = 1e-3
    def setSafe_wait_highZ(b):
        temp = atto.condenser.getTemperature()
        if temp >Tthresh:
            # atto.disconnect() 
            print( f"yikes, resevoir at {temp}C > max {Tthresh}")
            mag_highZ.shutdown()
            raise RuntimeError(f"shut down bc resevoir at {temp}C > max {Tthresh}")

        tic = time.time()
        while not mag_highZ.check_field_highZ(b, ATOL):
            time.sleep(0.1)
            mag_highZ.set_field_highZ(b)
            time.sleep(0.1)
            print(f"waiting for mag_highZ for {time.time()-tic}")

        mag_highZ.BhighZ_set = b
    
    mag_highZ.setSafe_wait_highZ = setSafe_wait_highZ

except:
    print("sagnac3.0: no magnet aps100")




try: # Keithly
    from pymeasure.instruments.keithley import Keithley2400
    keith1 = Keithley2400("GPIB::26")
    keith2 = Keithley2400("GPIB::24")

except:
    print( "sagnac3.0: no keith")



try: # Owon osciloscope
    import vds1022 as owon
    vds = owon.VDS1022(debug=0)
    # usage: vds.fetch().ch1.rms()
except:
    print("sagnac3.0: no owon")