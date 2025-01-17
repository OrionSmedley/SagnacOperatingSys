from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa
# from .instruments.AMI420 import AMI420
# from sagnac.instruments import APS100
import atto_device.CRYO2100 as cr

class magnet:
    def __init__(self):
        self.Bx_set, self.By_set, self.Bz_set = 0, 0, 0
        self.B_set = np.sqrt(self.Bx_set**2 + self.By_set**2 + self.Bz_set**2)
        print(f"first check: B magnitude is: {self.B_set}")
        # self._phi = (np.arctan2(self.By_set, self.Bx_set)*180/np.pi) % 360
        # self._theta = (np.arctan2(np.sqrt(self.Bx_set**2 + self.By_set**2), self.Bz_set)*180/np.pi) % 360
    
    def set_phi(self, phi = None):
        # how do we determine the sign of B? cuz there's an angle sign offset of 180 for negative B
        print(f"second check: B magnitude is: {self.B_set} and phi is: {self._phi}")
        if phi == None: 
            # ang_sign_offset = 0 if self._B_sign > 0 else 180
            self._phi = (np.arctan2(self.By_set, self.Bx_set)*180/np.pi) % 360
            print(f"now phi is: {self._phi}")
        else:
            self._phi = phi
            self.Bx_set = np.round(self.B_set*np.cos(phi*np.pi/180)*np.sin(self._theta*np.pi/180), 5)
            self.By_set = np.round(self.B_set*np.sin(phi*np.pi/180)*np.sin(self._theta*np.pi/180), 5)
            self.Bz_set = np.round(self.B_set*np.cos(self._theta*np.pi/180), 5)
            print(f"now phi is: {self._phi}")
    def get_phi(self):
        # self._phi = (np.arctan2(self.By_set, self.Bx_set)*180/np.pi) % 360
        return (np.arctan2(self.By_set, self.Bx_set)*180/np.pi) % 360

    phi = property(get_phi,set_phi)

    def set_theta(self, theta = None):
        if theta == None:
            B = np.sqrt(self.Bx_set**2 + self.By_set**2 + self.Bz_set**2)
            # ang_sign_offset = 0 if self._B_sign > 0 else 180
            self._theta = (np.arctan2(np.sqrt(self.Bx_set**2 + self.By_set**2), self.Bz_set)*180/np.pi) % 360
        else:
            self._theta = theta
            self.Bx_set = np.round(self.B_set*np.cos(self._phi*np.pi/180)*np.sin(theta*np.pi/180), 5)
            self.By_set = np.round(self.B_set*np.sin(self._phi*np.pi/180)*np.sin(theta*np.pi/180), 5)
            self.Bz_set = np.round(self.B_set*np.cos(theta*np.pi/180), 5)


    def get_theta(self):
        return self._theta
    
    theta = property(get_theta, set_theta)

    def set_field(self):
        self.set_field_cartesian(self.Bx_set, self.By_set, self.Bz_set)

    def set_field_cartesian(self, Bx, By, Bz):
        """
        Sets the field using a cartesian basis
        """
        # if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim: #np.sqrt returns positive square root
        #     log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
        #     raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)
        
        # # self.device.magnet.setHSetPoint3D(Bz, By, Bx)
        # self.device_x.set_field(Bx)
        # self.device_2.set_channel(1) # z 
        # self.device_2.set_field(Bz)
        # self.device_2.set_channel(2) # y
        # self.device_2.set_field(By)
        pass
        
    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
        # self.device_2.set_channel(1) # z
        # Bz = self.device_2.get_field()
        # self.device_2.set_channel(2) # y
        # By = self.device_2.get_field()
        # Bx = self.device_x.get_field()
        # return Bx, By, Bz
        pass

magnet = magnet()

magnet.B_set = 6
magnet.set_phi(45)
magnet.set_theta(45)
print(f"Vector components are: x= {magnet.Bx_set} , y= {magnet.By_set}, z= {magnet.Bz_set}")
print(magnet.phi)
print(magnet.theta)

# magnet.B_set = -6
# magnet.set_phi(45)
# magnet.set_theta(45)

# magnet.Bx_set = 3
# magnet.By_set = 3
# magnet.Bz_set = np.sqrt(18)

# print(f"Magnitude is: {magnet.B_set} and Vector components are: x= {magnet.Bx_set} , y= {magnet.By_set}, z= {magnet.Bz_set}")
# print(magnet.phi)
# print(magnet.theta)

# magnet.set_phi()
# magnet.set_theta()

# print(f"Vector components are: x= {magnet.Bx_set} , y= {magnet.By_set}, z= {magnet.Bz_set}")
# print(magnet.phi)
# print(magnet.theta)

# magnet.phi = 15
# magnet.theta = 15

# print(f"Vector components are: x= {magnet.Bx_set} , y= {magnet.By_set}, z= {magnet.Bz_set}")
# print(magnet.phi)
# print(magnet.theta)


