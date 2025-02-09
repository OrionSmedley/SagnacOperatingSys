from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa
from .instruments.AMI420 import AMI420
from sagnac.instruments import APS100
import atto_device.CRYO2100 as cr

class Magnet:
    ATOL = 1e-3
    Tthresh = 4.2
    def __init__(self):
        self.device_x = APS100("COM4")
        self.device_2 = APS100("COM5")
        # device 2 channel 1 is Z
        # device 2 channel 2 is Y

        # limit such that below this field change the magnet does not actually change field,
        # to limit commands sent to the magnet
        self._field_difference_cutoff = 0 #1e-5 # 0.1 G

    

        self._field_mag_lim = 9.9 # set to 1? bootleg version is kG, previous auttodry gui was T

        self._B_sign = 1

        self.atto = cr("192.168.1.1")
        self.atto.connect()
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
        if self.device_x.connection and self.device_x.connection.is_open:
            self.device_x.disconnect()
        if self.device_2.connection and self.device_2.connection.is_open:
            self.device_2.disconnect()
        self.device_x.connect()
        self.device_x.write_command("REMOTE")
        self.device_2.connect()
        self.device_2.write_command("REMOTE")
        Bx, By, Bz = self.get_field_cartesian()
        print( "conecting. The field is", np.sqrt(Bx*Bx + By*By + Bz*Bz))
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            self.device_x.disconnect()
            self.device_2.disconnect()
            print( "Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
            raise ValueError("Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
        
        self.Bx, self.By, self.Bz = self.get_field_cartesian()



    def setSafe_wait(self, junk = 0):
        temp = self.atto.condenser.getTemperature()
        if temp > self.Tthresh:
            # atto.disconnect() 
            print( f"yikes, resevoir at {temp}C > max {self.Tthresh}")
            self.shutdown()
            raise RuntimeError(f"shut down bc resevoir at {temp}C > max {self.Tthresh}")

        tic = time()
        Bx_init, By_init, Bz_init = self.get_field_cartesian()
        # print(f"Bz initial: {Bx_init, By_init, Bz_init}")
        if not np.abs(self.Bz) > np.abs(Bz_init): 
            # print("entering if")
            while not self.check_field_cartesian(Bx_init, By_init, self.Bz, 10*self.ATOL):
                # print("waiting for z to ramp down")
                sleep(0.1)
                self.set_field_cartesian(Bx_init,By_init,self.Bz)
                sleep(0.1)
                print(f"waiting for z to ramp down {time()-tic}")

        while not self.check_field_cartesian(self.Bx, self.By, self.Bz, self.ATOL):
            sleep(0.1)
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
        self.device_x.set_field(Bx)
        self.device_2.set_channel(1) # z 
        self.device_2.set_field(Bz)
        self.device_2.set_channel(2) # y
        self.device_2.set_field(By)
        
    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
        self.device_2.set_channel(1) # z
        Bz = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By = self.device_2.get_field()
        Bx = self.device_x.get_field()
        return Bx, By, Bz

    def check_field_cartesian(self, Bx_set, By_set, Bz_set, ATOL):
        """Checks the current field value to make sure it is within absolute tolerance of setpoint """
        # Bx_current = self.device.magnet.getH(2)
        # By_current = self.device.magnet.getH(1)
        # Bz_current = self.device.magnet.getH(0)
        self.device_2.set_channel(1) # z
        Bz_current = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By_current = self.device_2.get_field()
        Bx_current = self.device_x.get_field()

        if np.isclose(Bx_set,Bx_current, atol=ATOL) and np.isclose(By_set,By_current,atol=ATOL) and np.isclose(Bz_set, Bz_current, atol=ATOL):
            # log.info("Field is not close to the setpoint")
            log.info("field is close to the setpoint")
            return True
        else:
            log.info(f"{Bx_current}, {By_current}, {Bz_current}")
            return False



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
