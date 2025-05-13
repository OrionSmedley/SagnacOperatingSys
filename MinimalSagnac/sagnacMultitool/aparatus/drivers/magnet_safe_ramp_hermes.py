from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa

from aparatus.sagnac4 import TM620

class MagPowSup:
    
    def __init__(self, IPAddress):
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(f"TCPIP0::{IPAddress}::4444::SOCKET")
        self.instrument.read_termination = '\r\n'
        self.instrument.write_termination = '\r\n'
    
    def disconnect(self):
        if self.instrument:
            self.instrument.close()
            print("Disconnected from the instrument.")
    
    def query(self, command):
        return self.instrument.query(command)

    def write(self, command):
        self.instrument.write(command)

    def set_channel(self, channel):
        self.write(f'CHAN {int(channel)}')
        res = self.query('CHAN?')
        return res

    def get_field(self):
        value = np.nan
        while np.isnan(value):
            try:
                res = self.query('IMAG?')
                value = float(res.replace('kG', ''))
                return value
            except:
                value =  np.nan
                sleep(1)
                
    def pause_field(self):
        response = self.query('SWEEP?')
        # print(f"Response is {response}")
        while response != 'Pause':
            self.write('SWEEP PAUSE')
            sleep(0.05)
            response = self.query('SWEEP?')
            print(f"Mag ramp now set to {response}")    
        
    def temp_check(self, Tthresh):
        Tmag = TM620.Tmag
        if Tmag > float(Tthresh):
            print(f"Woah magnet temp is higher than {Tthresh}. Pausing ramp to cool down.")
            while Tmag > (Tthresh):
                sleep(2)
                print(f"Waiting for magnet to cool from {Tmag} to {(Tthresh)}")
                return False
        else:
            return True        
            
    def set_field(self, field):
        current_field = self.get_field()
        sleep(0.1)
        if field - current_field > 0.001:
            self.write(f'ULIM {field}')
            sleep(0.1)
            self.write('SWEEP UP')
        elif field - current_field < -0.001:
            self.write(f'LLIM {field}')
            sleep(0.1)
            self.write('SWEEP DOWN')
        else:
            pass

    def check_field(self, set_field, tol = 0.001):
        current_field = self.get_field()
        if abs(set_field - current_field) > tol:
            return False
        else:
            return True    

    def is_ramping(self):
        check = self.query('SWEEP?')
        # print(f"Ramping check is {check}")
        return check

    def zero_field(self):
        self.write('SWEEP ZERO')

class Magnet:
    
    def __init__(self):
        self.device_z = MagPowSup('169.254.62.187')
        self.device_2 = MagPowSup('169.254.62.188')
        # device 2 channel 1 is X
        # device 2 channel 2 is Y

        # limit such that below this field change the magnet does not actually change field,
        # to limit commands sent to the magnet
        self._field_difference_cutoff = 0 #1e-5 # 0.1 G

        self._field_mag_lim = 9.5 # set to 1? bootleg version is kG, previous auttodry gui was T

        self._B_sign = 1 
        
        self.ATOL = 1e-3
        self._Toverheat = 4.3
        self._Tcooling = (self._Toverheat - 0.2)
        self._Tflag = (self._Toverheat - 0.1)
        self._flag = 1

        # self.Bx_set, self.By_set, self.Bz_set = self.get_field_cartesian()
        # self.B_set, self.phi_set, self.theta_set = self.get_field_polar()


   
    #######################################
    ############### Fancy #################
    def get_B(self):
        """Returns the magnitude of the field."""

        return np.sqrt(self.Bx**2 + self.By**2 + self.Bz**2)

    def set_B(self, val):
        """Sets the magnitude of the field while preserving direction."""
        current_B = self.B
        if current_B != 0:
            scale = val / current_B
            self.Bx *= scale
            self.By *= scale
            self.Bz *= scale
        
        else:
            raise ValueError("Cannot set B when the field is zero (direction undefined).")

    def get_phi(self):
        """Returns the azimuthal angle (phi) in degrees."""
        return np.degrees(np.arctan2(self.By, self.Bx)) % 360

    def set_phi(self, val):
        """Sets phi while keeping the magnitude and theta fixed."""
        b = self.B
        theta = np.radians(self.theta)
        rad_phi = np.radians(val)
        self.Bx = b * np.cos(rad_phi) * np.sin(theta)
        self.By = b * np.sin(rad_phi) * np.sin(theta)
        # Z remains unchanged to preserve theta
        self.Bz = b * np.cos(theta)

    def get_theta(self):
        """Returns the polar angle (theta) in degrees."""
        return np.degrees(np.arctan2(np.hypot(self.Bx, self.By), self.Bz)) % 360

    def set_theta(self, val):
        """Sets theta while keeping the magnitude and phi fixed."""
        b = self.B
        phi = np.radians(self.phi)
        rad_theta = np.radians(val)
        self.Bx = b * np.cos(phi) * np.sin(rad_theta)
        self.By = b * np.sin(phi) * np.sin(rad_theta)
        self.Bz = b * np.cos(rad_theta)

    # def get_cartesian(self):
    #     """Returns the current (Bx, By, Bz) as a tuple."""
    #     return self.Bx, self.By, self.Bz

    # def set_cartesian(self, Bx, By, Bz):
    #     """Sets the field directly using Cartesian coordinates."""
    #     self.Bx, self.By, self.Bz = Bx, By, Bz

    # Properties for cleaner access
    B = property(get_B, set_B)
    phi = property(get_phi, set_phi)
    theta = property(get_theta, set_theta)

    #######################################
    ############### Old Hardware connections #################

    def connect(self):
        self.device_z.write("REMOTE")
        self.device_2.write("REMOTE")
        Bx, By, Bz = self.get_field_cartesian()
        print("Connecting. The field is", np.sqrt(Bx*Bx + By*By + Bz*Bz))
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            self.device_z.disconnect()
            self.device_2.disconnect()
            print("Bmag vector is larger than 0.95 T! Don't touch anything else! call Kelly")
            raise ValueError("Bmag vector is larger than 0.95 T! Don't touch anything else! call Kelly")
        
        self.Bx, self.By, self.Bz = self.get_field_cartesian()
        
    def setSafe_wait(self, junk = 0):
        
        tic = time()
        Bx_init, By_init, Bz_init = self.get_field_cartesian()
        # print(f"Bz initial: {Bx_init, By_init, Bz_init}")
        mag_safe = self.check_temps()
        # print(f"Mag safe 1 is {mag_safe}")
        if mag_safe != None:
            if not np.abs(self.Bz) > np.abs(Bz_init): 
                # print("entering if")
                while not self.check_field_cartesian(Bx_init, By_init, self.Bz, 10*self.ATOL):
                    # print("waiting for z to ramp down")
                    mag_safe = self.check_temps()
                    # print(f"Mag safe 3 is {mag_safe}")
                    sleep(0.1)
                    if mag_safe == True:
                        self.set_field_cartesian(Bx_init,By_init,self.Bz)
                        sleep(0.1)
                        print(f"waiting for z to ramp down {time()-tic}")
            else:
                while not self.check_field_cartesian(self.Bx, self.By, self.Bz, self.ATOL):
                    mag_safe = self.check_temps()
                    # print(f"Mag safe 4 is {mag_safe}")
                    sleep(0.1)
                    if mag_safe == True:
                        self.set_field_cartesian(self.Bx, self.By, self.Bz)
                        sleep(0.1)
                        print(f"waiting for mag for {time()-tic}")


    # The methods below are unchanged from the OG 

    def set_field_cartesian(self, Bx, By, Bz):
        """
        Sets the field using a cartesian basis
        """
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim: #np.sqrt returns positive square root
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)
        
        # self.device.magnet.setHSetPoint3D(Bz, By, Bx)
        self.device_z.set_field(Bz)
        self.device_2.set_channel(1) # x 
        self.device_2.set_field(Bx)
        self.device_2.set_channel(2) # y
        self.device_2.set_field(By)
        
    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
        self.device_2.set_channel(1) # x
        Bx = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By = self.device_2.get_field()
        Bz = self.device_z.get_field()
        return Bx, By, Bz

    def check_field_cartesian(self, Bx_set, By_set, Bz_set, ATOL):
        """Checks the current field value to make sure it is within absolute tolerance of setpoint """
        # Bx_current = self.device.magnet.getH(2)
        # By_current = self.device.magnet.getH(1)
        # Bz_current = self.device.magnet.getH(0)
        self.device_2.set_channel(1) # x
        Bx_current = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By_current = self.device_2.get_field()
        Bz_current = self.device_z.get_field()
        
        print(f"Bx, By, Bz is currently {Bx_current},{By_current},{Bz_current}")

        if np.isclose(Bx_set, Bx_current, atol=ATOL) and np.isclose(By_set, By_current,atol=ATOL) and np.isclose(Bz_set, Bz_current, atol=ATOL):
            # log.info("Field is not close to the setpoint")
            log.info("field is close to the setpoint")
            return True
        else:
            log.info(f"{Bx_current}, {By_current}, {Bz_current}")
            return False
        
    def check_temps(self):
        """Checks the Magnet Thermometer Temperature to know if the ramp rate needs to be paused"""
        bigcheck = self.device_z.temp_check(self._Toverheat)
        
        # print(f"bigcheck 1 is {bigcheck}")
            
        if bigcheck == True:
            secondcheck = self.device_z.temp_check((self._Tflag))        
            if secondcheck == False or self._flag == 2:
                self._flag = 2
                print(f"Flag is {self._flag}")
                while self._flag != 1:
                    # print(f"Threshold is {self._Tcooling}")
                    print(f"Flag check == {self._flag}")
                    zcheck = self.device_z.temp_check(self._Tcooling)
                    
                    # print(f"Zcheck 1 is {zcheck}")
                    
                    if zcheck == True:
                        self._flag = 1
                        print(f"FLAG IS NOW {self._flag}")
                        return True
                    
                    else:
                        check1 = self.device_z.is_ramping()
                        # print(f"Check1 is {check1}")
                        if check1 != "Pause" or check1 != "Standby":
                            self.device_z.pause_field()
                        
                        self.device_2.set_channel(1) # x check
                        check2 = self.device_2.is_ramping()
                        # print(f"Check2 is {check2}")
                        if check2 == "Pause" or check2 != "Standby":
                            self.device_2.pause_field()
                            
                        self.device_2.set_channel(2) # y check
                        check3 = self.device_2.is_ramping()
                        # print(f"Check3 is {check3}")
                        if check3 != "Pause" or check3 != "Standby":
                            self.device_2.pause_field()

                        zcheck = self.device_z.temp_check(self._Tcooling)
                        
                        return False
            elif secondcheck == True:
                if self._flag == 1:
                    return True 
                
        else: 
            print("Magnet is way too hot, stop this")
            return None



# magnet = Magnet(1, 0, 0)

# print("Initial B:", magnet.B)
# print("Initial Phi:", magnet.phi)
# print("Initial Theta:", magnet.theta)

# magnet.phi = 90
# print("After setting phi to 90°:", magnet.get_cartesian())

# magnet.theta = 45
# print("After setting theta to 45°:", magnet.get_cartesian())

# magnet.B = 2
# print("After setting magnitude to 2:", magnet.get_cartesian())
