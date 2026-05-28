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

    def dc1(v=None):
        Vrange = myHF2LI.sigouts[0].range()
        if v is not None:
            myHF2LI.sigouts[0].offset(v / Vrange)
        return myHF2LI.sigouts[0].offset() * Vrange
    def ac1(v=None):
        Vrange = myHF2LI.sigouts[0].range()
        if v is not None:
            myHF2LI.sigouts[0].amplitudes[8-1](v / Vrange)
        return myHF2LI.sigouts[0].amplitudes[8-1]() * Vrange
    myHF2LI.dc1 = dc1
    myHF2LI.ac1 = ac1

    def dc2(v=None):
        Vrange = myHF2LI.sigouts[1].range()
        if v is not None:
            myHF2LI.sigouts[1].offset(v / Vrange)
        return myHF2LI.sigouts[1].offset() * Vrange

    def ac2(v=None):
        Vrange = myHF2LI.sigouts[1].range()
        if v is not None:
            myHF2LI.sigouts[1].amplitudes[7-1](v / Vrange)
        return myHF2LI.sigouts[1].amplitudes[7-1]() * Vrange
    myHF2LI.dc2 = dc2
    myHF2LI.ac2 = ac2

    def zurich(mode = "Sagnac"):
        dem = myHF2LI.dem
        if mode == "Sagnac":      return {"mode":mode,"ac1":myHF2LI.ac1(),"dc1":myHF2LI.dc1(),"diff1":myHF2LI.sigins[1-1].diff(),"ac2":myHF2LI.ac2(),"dc2":myHF2LI.dc2(),"diff2":myHF2LI.sigins[2-1].diff(),"TX1":dem(1-1)['x'][0],"TY1":dem(1-1)['y'][0],"TX2":dem(2-1)['x'][0],"TY2":dem(2-1)['y'][0],"X2":dem(3-1)['x'][0],"Y2":dem(3-1)['y'][0],"X1":dem(4-1)['x'][0],"Y1":dem(4-1)['y'][0],"XC+M":dem(5-1)['x'][0],"YC+M":dem(5-1)['y'][0],"XC-M":dem(6-1)['x'][0],"YC-M":dem(6-1)['y'][0],"ThetaK":0.543*np.arctan(dem(4-1)['x'][0]/dem(3-1)['y'][0]),"DeltaThetaK":0.543*dem(5-1)['x'][0]/dem(3-1)['y'][0],"DeltaThetaK_DualSideband":0.543*(dem(5-1)['x'][0] + dem(6-1)['x'][0]) / (2 * dem(2)['y'][0]) }
        elif mode == "Transport": return {"mode":mode,"ac1":myHF2LI.ac1(),"dc1":myHF2LI.dc1(),"diff1":myHF2LI.sigins[1-1].diff(),"ac2":myHF2LI.ac2(),"dc2":myHF2LI.dc2(),"diff2":myHF2LI.sigins[2-1].diff(),"TX1":dem(1-1)['x'][0],"TY1":dem(1-1)['y'][0],"TX2":dem(2-1)['x'][0],"TY2":dem(2-1)['y'][0],"X2":dem(3-1)['x'][0],"Y2":dem(3-1)['y'][0],"X1":dem(4-1)['x'][0],"Y1":dem(4-1)['y'][0],"XC+M":dem(5-1)['x'][0],"YC+M":dem(5-1)['y'][0],"XC-M":dem(6-1)['x'][0],"YC-M":dem(6-1)['y'][0]}
        else:
            print("Please select a mode for the zurich: 'Sagnac' or 'Transport'")

    # def dc(v=None):
    #     Vrange = myHF2LI.sigouts[1].range()
    #     if v is not None:
    #         myHF2LI.sigouts[1].offset(v / Vrange)
    #     return myHF2LI.sigouts[1].offset() * Vrange

    # def ac(v=None):
    #     Vrange = myHF2LI.sigouts[1].range()
    #     if v is not None:
    #         myHF2LI.sigouts[1].amplitudes[7-1](v / Vrange)
    #     return myHF2LI.sigouts[1].amplitudes[7-1]() * Vrange
    # myHF2LI.dc = dc
    # myHF2LI.ac = ac

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

try: # Zurich Aux Scanners

    #Scanner position property (can write and read scanner positions)
    #Uses myHF2LI.auxouts to set and record values as seen below.

    ### ATTENTION: THIS CLASS DOES NOT HAVE ANY INDICAITON OF CONNECTION TO THE SCANNING MODULE
    ### PLEASE CHECK THE POWER SUPPLIES ARE CORRECTLY CONNECTED TO MODULE BEFORE USING

    class scanners:
        def __init__(self):
            for i in range(4):
                myHF2LI.auxouts[i].outputselect(-1)
            self.x, self.y, self.z = 0, 0, 0

            import sys
            module_dir = r"D:\Github\SagnacOperatingSys\VecMagSagnac_control"
            sys.path.append(module_dir)
            import atto_device.CRYO2100 as cr
            atto = cr("192.168.1.1")
            atto.connect()
                    
        ### Sets and stores value for the x, y, z positions for the scans ###
        # aux[1-1] is the output for x
        # aux[2-1] is the output for y
        # aux[3-1] is the output for z

        def get_x(self): return myHF2LI.auxouts[1-1].value()
        
        def get_y(self): return myHF2LI.auxouts[2-1].value()
        
        def get_z(self): return myHF2LI.auxouts[3-1].value()
        
        def set_x(self,voltage):
            tsamp = atto.sample.getTemperature()
            if tsamp > 4:
                if voltage > 4 or voltage < 0:
                    print("Please set voltage to be within range of [0,4] volts")  
                else:
                    v_init = self.x
                    if v_init > voltage:
                        ramp = np.array(np.arange(v_init-0.005, voltage, -0.005))
                    else:
                        ramp = np.array(np.arange(v_init+0.005, voltage, 0.005))    
                    for i in range(int(len(ramp))):
                        myHF2LI.auxouts[1-1].offset(ramp[i])
                    myHF2LI.auxouts[1-1].offset(voltage)          
            elif tsamp <= 4:
                if voltage > 5 or voltage < 0:
                    print("Please set voltage to be within range of [0,10] volts")
                else:
                    v_init = self.x
                    if v_init > voltage:
                        ramp = np.array(np.arange(v_init-0.005, voltage, -0.005))
                    else:
                        ramp = np.array(np.arange(v_init+0.005, voltage, 0.005))    
                    for i in range(int(len(ramp))):
                        myHF2LI.auxouts[1-1].offset(ramp[i])
                    myHF2LI.auxouts[1-1].offset(voltage)

        def set_y(self,voltage):
            tsamp = atto.sample.getTemperature() 
            if tsamp > 4:
                if voltage > 4 or voltage < 0:
                    print("Please set voltage to be within range of [0,4] volts")  
                else:
                    v_init = self.y
                    if v_init > voltage:
                        ramp = np.array(np.arange(v_init-0.005, voltage, -0.005))
                    else:
                        ramp = np.array(np.arange(v_init+0.005, voltage, 0.005))    
                    for i in range(int(len(ramp))):
                        myHF2LI.auxouts[2-1].offset(ramp[i])
                    myHF2LI.auxouts[2-1].offset(voltage)          
            elif tsamp <= 4:
                if voltage > 5 or voltage < 0:
                    print("Please set voltage to be within range of [0,10] volts")
                else:
                    v_init = self.y
                    if v_init > voltage:
                        ramp = np.array(np.arange(v_init-0.005, voltage, -0.005))
                    else:
                        ramp = np.array(np.arange(v_init+0.005, voltage, 0.005))    
                    for i in range(int(len(ramp))):
                        myHF2LI.auxouts[2-1].offset(ramp[i])
                    myHF2LI.auxouts[2-1].offset(voltage)

        def set_z(self,voltage): 
            tsamp = atto.sample.getTemperature()
            if tsamp > 4:
                if voltage > 4 or voltage < 0:
                    print("Please set voltage to be within range of [0,4] volts")    
                else:
                    v_init = self.z
                    if v_init > voltage:
                        ramp = np.array(np.arange(v_init-0.005, voltage, -0.005))
                    else:
                        ramp = np.array(np.arange(v_init+0.005, voltage, 0.005))    
                    for i in range(int(len(ramp))):
                        myHF2LI.auxouts[3-1].offset(ramp[i])
                    myHF2LI.auxouts[3-1].offset(voltage)
            elif tsamp <= 4:
                if voltage > 5 or voltage < 0:
                    print("Please set voltage to be within range of [0,10] volts")
                else:
                    v_init = self.z
                    if v_init > voltage:
                        ramp = np.array(np.arange(v_init-0.005, voltage, -0.005))
                    else:
                        ramp = np.array(np.arange(v_init+0.005, voltage, 0.005))    
                    for i in range(int(len(ramp))):
                        myHF2LI.auxouts[3-1].offset(ramp[i])
                    myHF2LI.auxouts[3-1].offset(voltage)

        x = property(get_x, set_x)
        y = property(get_y, set_y)
        z = property(get_z, set_z)
        def get_positions(self):return {"x": self.x,"y": self.y,"z": self.z}
        positions = property(get_positions)

    scanner = scanners()

except:
    print("sagnac3.0: no scanners")


try: # Magnet

    import sys
    module_dir = r"D:\Github\SagnacOperatingSys\VecMagSagnac_control"
    sys.path.append(module_dir)
    # from sagnac.custom_instruments import vectorMagnetFullUSB
    # mag = vectorMagnetFullUSB()
    from sagnac.magnet_usb_safe_ramp_v2 import Magnet

    mag = Magnet(x_axis_tilt = 91.4, y_axis_tilt= 89.3, phi_offset=0.0)

    def field():
        return {"Bx":mag.Bx,"By":mag.By,"Bz":mag.Bz,"B":mag.B,"phi":mag.phi,"theta":mag.theta,"tilt_x":mag.x_axis_tilt,"tilt_y":mag.y_axis_tilt,"phi_offset":mag.phi_offset}

    def field_lab():
        return {"Bx":mag.Bx_lab,"By":mag.By_lab,"Bz":mag.Bz_lab,"B":mag.B_lab,"phi":mag.phi_lab,"theta":mag.theta_lab}
# #     x_axis_tilt is defined in the lab frame as the polar angle (in deg) from the z-axis into the positive x direction, defined here with defaults to 91.4 deg
# #     y_axis_tilt " " " " " " " " " " " " " " " " " " " " " " " " " " " " " " " " " " " " into the positive y direction, defined here with defaults to 89.3 deg
# #     phi_offset is used to rotate the xy-plane about the new sample frame z-axis, can be set later

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


try: #stepper
    from .drivers.ANC300 import ANC300
    stepper = ANC300()
    stepper.connect()
except:
    print("sagnac3.0: no stepper")

try: # Keithley
    import sys
    module_dir = r"C:\Users\luogroup\AppData\Roaming\Python\Python311\site-packages\pymeasure\instruments"
    sys.path.append(module_dir)
    from keithley.keithley2400 import Keithley2400 
    keith24 = Keithley2400("GPIB::24")
    keith25 = Keithley2400("GPIB::25")    
    keith26 = Keithley2400("GPIB::26")
    
    def k24():
        return {"V24":keith24.current[0],"I24":keith24.current[1]}
    def k25():
        return {"V25":keith25.current[0],"I25":keith25.current[1]}
    def k26():
        return {"V26":keith26.current[0],"I26":keith26.current[1]}

except:
    print( "sagnac3.0: no keith")

try: # Owon osciloscope
    import vds1022 as owon
    vds = owon.VDS1022(debug=0)
    # usage: vds.fetch().ch1.rms()
except:
    print("sagnac3.0: no owon")


try: # Laser controller LDC3900
    from aparatus.drivers.LDC3900 import LaserDriver
    laser = LaserDriver()

    def sled(mode = "Sagnac", laser_status = []):
        if mode == "Sagnac": 
            return {"T":laser.T, "LDI":laser.LDI, "LDV":laser.LDV}
        elif mode == "Scanning": 
            if int(len(laser_status)) != 3:
                raise ValueError("Please include as an argument: laser_status = [laserT, laserLDI, laserLDV]")
            else:
                return {"Tsamp": laser_status[0], "Tvti": laser_status[1], "Tres": laser_status[2]}
        else:
            raise ValueError("Please select mode: 'Scanning' or 'Sagnac'")
except:
    print("sagnac3.0: no LASER")

# dictionaries to evaluate for the CSVs
def logs(queueT = None, repeat = None, sampNumb = None, purpose = None):
    return {"queueT":queueT, "repeat":repeat, "sampNumb":sampNumb,"purpose":purpose,"now":pd.Timestamp.now(), "time": time.time()}

def temps(mode = "Sagnac", temps = []):
    if mode == "Sagnac":
        return {"Tsamp": atto.sample.getTemperature(), "Tvti": atto.vti.getTemperature(), "Tres": atto.condenser.getTemperature()}
    elif mode == "Scanning":
        if int(len(temps)) != 3:
            raise ValueError("Please include as an argument: temps = [Tsamp, Tvti, Tres]")
        else:
            return {"Tsamp": temps[0], "Tvti": temps[1], "Tres": temps[2]}
    else:
        raise ValueError("Please select mode: 'Scanning' or 'Sagnac'")