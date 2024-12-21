from time import sleep
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa
# from .instruments.AMI420 import AMI420
# from pymeasure.instruments.attocube import APS100
from .aps100 import APS100
import atto_device.CRYO2100 as cr
import time

class vectorMagnetFull:
    """
    Class to control all three axes of the vector magnet simultaneously.
    Uses the usual physics parameterization of the magnetic field.
    """

    def __init__(self, device):
        self.device = device
        self.device.connect()

        self._field_difference_cutoff = 0
        self._field_mag_lim = 1 # set to 1? originally 0.92 unit in T not kG
        self._B_sign = 1

    def set_field_polar(self, B, phi, theta):
        """
        Sets the field, accepting polar coordinates.
        """
        log.info('Setting to B, Phi, Theta: %g %g %g'%(B,phi,theta))
        
        phi = phi*np.pi/180
        theta = theta*np.pi/180

        Bx = np.round(B*np.cos(phi)*np.sin(theta), 5)
        By = np.round(B*np.sin(phi)*np.sin(theta), 5)
        Bz = np.round(B*np.cos(theta), 5)
        log.info(f"setting to Bx, By, Bz: {Bx}, {By}, {Bz}")

        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)

        if B < 0:
            self._B_sign = -1
        else:
            self._B_sign = 1
        self.device.magnet.setHSetPoint3D(Bz, By, Bx)

    def get_field_polar(self):
        """
        Returns the field in polar coordinates in the standard Physics parameterization
        in the order (B, phi, theta)
        """
        Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)

        B = self._B_sign * np.sqrt(Bx**2 + By**2 + Bz**2)
        ang_sign_offset = 0 if self._B_sign > 0 else 180
        phi = (np.arctan2(self._B_sign*By, self._B_sign*Bx)*180/np.pi + ang_sign_offset) % 360
        theta = (np.arctan2(np.sqrt(Bx**2 + By**2), self._B_sign*Bz)*180/np.pi+ ang_sign_offset) % 360

        return B, phi, theta

    def check_field_polar(self, B, phi, theta, ATOL):
        """Checks the current field value to make sure it is within absolute tolerance of setpoint"""
        phi = phi*np.pi/180
        theta = theta*np.pi/180

        Bx_set = np.round(B*np.cos(phi)*np.sin(theta), 5)
        By_set = np.round(B*np.sin(phi)*np.sin(theta), 5)
        Bz_set = np.round(B*np.cos(theta), 5)

        Bz_current, By_current, Bx_current = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)

        if (np.isclose(Bx_set,Bx_current, atol=ATOL) and
            np.isclose(By_set,By_current,atol=ATOL) and
            np.isclose(Bz_set, Bz_current, atol=ATOL)):
            log.info("Field is close to the setpoint")
            log.info(f"magnet finally at Bx, By, Bz: {Bx_current}, {By_current}, {Bz_current}")
            return True
        else:
            log.info("field is not close to the setpoint")
            log.info(f"magnet still at Bx, By, Bz: {Bx_current}, {By_current}, {Bz_current}")
            log.info(f"Try again setting to Bx, By, Bz: {Bx_set}, {By_set}, {Bz_set}")
            return False

    def set_field_cartesian(self, Bx, By, Bz):
        """
        Sets the field using a cartesian basis
        """
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)
        self.device.magnet.setHSetPoint3D(Bz, By, Bx)

    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
        return Bx, By, Bz

    def check_field_cartesian(self, Bx_set, By_set, Bz_set, ATOL):
        """Checks the current field value to make sure it is within absolute tolerance of setpoint """
        Bx_current = self.device.magnet.getH(2)
        By_current = self.device.magnet.getH(1)
        Bz_current = self.device.magnet.getH(0)

        if (np.isclose(Bx_set,Bx_current, atol=ATOL) and
            np.isclose(By_set,By_current,atol=ATOL) and
            np.isclose(Bz_set, Bz_current, atol=ATOL)):
            log.info("field is close to the setpoint")
            return True
        else:
            log.info(f"{Bx_current}, {By_current}, {Bz_current}")
            return False

    def is_ramping(self):
        return self.device.magnet.getFieldControl(0)  # Example or pass

    def is_holding(self):
        return self.magnet_x.is_holding() or self.magnet_y.is_holding() or self.magnet_z.is_holding()

    def is_zeroing(self):
        return self.magnet_x.is_zeroing() or self.magnet_y.is_zeroing() or self.magnet_z.is_zeroing()

    def is_quenched(self):
        return self.magnet_x.is_quenched() or self.magnet_y.is_quenched() or self.magnet_z.is_quenched()

    def is_paused(self):
        return self.magnet_x.is_paused() or self.magnet_y.is_paused() or self.magnet_z.is_paused()

    def shutdown(self):
        """
        Shuts down each of the magnets individually
        """
        log.info("Shutting down all of the magnets")
        self.device.action.shutdown()

    def set_magnet_field(self, magnet, setPoint):
        # magnet is 0, 1, 2
        # field strength
        # I wrote this for self.z_magnet.field = self.saturating_field in heterodyneProcedure
        self.device.magnet.setHSetPoint(magnet, setPoint)



class vectorMagnetFullUSB:
    """
    Class to control all three axes of the vector magnet simultaneously.
    Uses the usual physics parameterization of the magnetic field.
    """
    temp_threshold = 4.5
    def __init__(self):
        # in this case device = APS100("port")

        self.device_x = APS100("COM4")
        self.device_2 = APS100("COM5")
        # if self.device_x.connection and self.device_x.connection.is_open:
        # self.device_x.disconnect()
        # if self.device_2.connection and self.device_2.connection.is_open:
        # self.device_2.disconnect()
        self.atto = cr("192.168.1.1")
        self.atto.connect()
        

        # device 2 channel 1 is Z
        # device 2 channel 2 is Y

        # limit such that below this field change the magnet does not actually change field,
        # to limit commands sent to the magnet
        self._field_difference_cutoff = 0 #1e-5 # 0.1 G

        # TODO: should we reset the current limit of the z magnet or just
        # trust that the checking in this class will always be OK?

        self._field_mag_lim = 1 # set to 1? originally 0.92 unit in T not kG

        self._B_sign = 1
    
    def connect(self):
        if self.device_x.connection and self.device_x.connection.is_open:
            self.device_x.disconnect()
        if self.device_2.connection and self.device_2.connection.is_open:
            self.device_2.disconnect()
        self.device_x.connect()
        self.device_x.send_command("REMOTE")
        self.device_2.connect()
        self.device_2.send_command("REMOTE")


    ####################################################################################
    ############################## safe wait Additions #################################
    def safeSetWait(
            self,
            set_func,
            get_func,
            target_values,
            poll_interval=0.5,
            timeout=30.0,
            compare_func=None
        ):

        """
        1) Checks temperature: if below threshold, proceeds; else ramps to 0 and raises error.
        2) Calls set_func(*target_values).
        3) Polls get_func() until the result is close to 'target_values'
           or until 'timeout' expires.

        If compare_func is None, uses np.allclose() with default tolerance.
        Otherwise, compare_func(current_values, target_values) -> bool
        """

        # --- FIX 1: use self.atto for temperature, and match variable naming ---
        magTemp = float(self.atto.condenser.getTemperature())  # <-- CHANGED
        if magTemp < self.temp_threshold:                       # <-- CHANGED (was magtemp)
            # If safe: proceed with target_values
            # (We do NOT have bx,by,bz here, so we just set after the temperature check.)
            pass
        else:
            # Ramp mag to 0,0,0 and raise an error properly
            # Because we don't have 'self.magnet', let's just call set_func(0,0,0)
            set_func(0, 0, 0)  # ramp to zero
            raise RuntimeError("Reservoir temperature higher than threshold!")  # <-- CHANGED

        # 2) Now actually set to the requested field
        set_func(*target_values)

        start_time = time.time()
        while True:
            current_values = get_func()

            # 3) Check if we're close enough
            if compare_func is None:
                # naive approach using np.allclose
                if np.allclose(current_values, target_values, atol=3e-4):
                    log.info(f"Field converged to {current_values}")
                    return
            else:
                # custom comparison logic
                if compare_func(current_values, target_values):
                    log.info(f"Field converged to {current_values}")
                    return

            if (time.time() - start_time) > timeout:
                msg = (f"Timed out waiting for setpoint {target_values}. "
                       f"Last reading was {current_values}")
                print(msg)
                raise TimeoutError(msg)

            time.sleep(poll_interval)

    @staticmethod
    def angles_are_close(angle1, angle2, atol=0.1):
        """
        Returns True if angle1 and angle2 (in degrees) differ by less than atol
        when accounting for 0 = 360, etc.
        """
        diff = abs(angle1 - angle2) % 360
        if diff > 180:
            diff = 360 - diff
        return diff <= atol

    def polar_compare_func(self, current, target, atol_B=3e-4, atol_angle=0.5):
        """
        Compare (B, phi, theta) with wrap-around for angles.
        """
        (Bc, phic, thetac) = current
        (Bt, phit, thetat) = target
        close_B = (abs(Bc - Bt) <= atol_B)
        close_phi = self.angles_are_close(phic, phit, atol=atol_angle)
        close_theta = self.angles_are_close(thetac, thetat, atol=atol_angle)
        return (close_B and close_phi and close_theta)
    ############################## safe wait Additions #################################
    ####################################################################################


    def set_field_polar(self, B, phi, theta):
        """
        Sets the field, accepting polar coordinates.
        """
        log.info('Setting to B, Phi, Theta: %g %g %g'%(B,phi,theta))
        
        phi = phi*np.pi/180
        theta = theta*np.pi/180

        Bx = np.round(B*np.cos(phi)*np.sin(theta), 5)
        By = np.round(B*np.sin(phi)*np.sin(theta), 5)
        Bz = np.round(B*np.cos(theta), 5)
        log.info(f"setting to Bx, By, Bz: {Bx}, {By}, {Bz}")

        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)

        if B < 0:
            self._B_sign = -1
        else:
            self._B_sign = 1

        self.device_2.set_channel(2) # y
        self.device_2.set_field(By)
        self.device_x.set_field(Bx)
        self.device_2.set_channel(1) # z 
        self.device_2.set_field(Bz)

    def get_field_polar(self):
        """
        Returns the field in polar coordinates in the standard Physics parameterization
        in the order (B, phi, theta)
        """
        self.device_2.set_channel(1) # z
        Bz = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By = self.device_2.get_field()
        Bx = self.device_x.get_field()

        B = self._B_sign * np.sqrt(Bx**2 + By**2 + Bz**2)
        ang_sign_offset = 0 if self._B_sign > 0 else 180
        phi = (np.arctan2(self._B_sign*By, self._B_sign*Bx)*180/np.pi + ang_sign_offset) % 360
        theta = (np.arctan2(np.sqrt(Bx**2 + By**2), self._B_sign*Bz)*180/np.pi+ ang_sign_offset) % 360

        return B, phi, theta

    def check_field_polar(self, B, phi, theta, ATOL):
        """
        Checks the current field value to make sure it is within absolute tolerance of setpoint
        """
        phi = phi*np.pi/180
        theta = theta*np.pi/180

        Bx_set = np.round(B*np.cos(phi)*np.sin(theta), 5)
        By_set = np.round(B*np.sin(phi)*np.sin(theta), 5)
        Bz_set = np.round(B*np.cos(theta), 5)

        self.device_2.set_channel(1) # z
        Bz_current = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By_current = self.device_2.get_field()
        Bx_current = self.device_x.get_field()

        if (np.isclose(Bx_set,Bx_current, atol=ATOL) and
            np.isclose(By_set,By_current,atol=ATOL) and
            np.isclose(Bz_set, Bz_current, atol=ATOL)):
            log.info("Field is close to the setpoint")
            log.info(f"magnet finally at Bx, By, Bz: {Bx_current}, {By_current}, {Bz_current}")
            return True
        else:
            log.info("field is not close to the setpoint")
            log.info(f"magnet still at Bx, By, Bz: {Bx_current}, {By_current}, {Bz_current}")
            log.info(f"Try again setting to Bx, By, Bz: {Bx_set}, {By_set}, {Bz_set}")
            return False

    def set_field_cartesian(self, Bx, By, Bz):
        """
        Sets the field using a cartesian basis
        """
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)

        self.device_x.set_field(Bx)
        self.device_2.set_channel(1) # z 
        self.device_2.set_field(Bz)
        self.device_2.set_channel(2) # y
        self.device_2.set_field(By)
        # Removed incomplete "while not np.isclose()" line # <-- CHANGED minimally by commenting or removing

    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        self.device_2.set_channel(1) # z
        Bz = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By = self.device_2.get_field()
        Bx = self.device_x.get_field()
        return Bx, By, Bz

    def check_field_cartesian(self, Bx_set, By_set, Bz_set, ATOL):
        """
        Checks the current field value to make sure it is within absolute tolerance of setpoint 
        """
        self.device_2.set_channel(1) # z
        Bz_current = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By_current = self.device_2.get_field()
        Bx_current = self.device_x.get_field()

        if (np.isclose(Bx_set,Bx_current, atol=ATOL) and
            np.isclose(By_set,By_current,atol=ATOL) and
            np.isclose(Bz_set, Bz_current, atol=ATOL)):
            log.info("field is close to the setpoint")
            return True
        else:
            log.info(f"{Bx_current}, {By_current}, {Bz_current}")
            return False

    def is_ramping(self):
        return

    def is_holding(self):
        # return self.magnet_x.is_holding() or self.magnet_y.is_holding() or self.magnet_z.is_holding()
        return
    
    def is_zeroing(self):
        # return self.magnet_x.is_zeroing() or self.magnet_y.is_zeroing() or self.magnet_z.is_zeroing()
        return
    def is_quenched(self):
        # return self.magnet_x.is_quenched() or self.magnet_y.is_quenched() or self.magnet_z.is_quenched()
        return
    def is_paused(self):
        # return self.magnet_x.is_paused() or self.magnet_y.is_paused() or self.magnet_z.is_paused()
        return
    def shutdown(self):
        """
        Shuts down each of the magnets individually
        """
        log.info("Shutting down all of the magnets")
        self.device_x.zero_field()
        self.device_2.set_channel(1) # z
        self.device_2.zero_field()


        self.device_2.set_channel(2) # y
        self.device_2.zero_field()

        self.device_x.disconnect()
        self.device_2.disconnect()

    def set_magnet_field(self, magnet, setPoint):
        # magnet is 0, 1, 2, Bz, By, Bx
        # field strength
        # I wrote this for self.z_magnet.field = self.saturating_field in heterodyneProcedure
        # self.device.magnet.setHSetPoint(magnet, setPoint)
        if magnet == 0:
            self.device_2.set_channel(1)
            self.device_2.set_field(setPoint)
        elif magnet == 1:
            # self.device_y.set_field(setPoint)
            self.device_2.set_channel(2)
            self.device_2.set_field(setPoint)
        elif magnet == 2:
            self.device_x.set_field(setPoint)


    # --------------------------------------------------------------------------
    # OPTIONAL: Two shortcut methods so external code can simply call these
    # --------------------------------------------------------------------------
    def safeWaitCart(self, Bx, By, Bz, poll_interval=0.1, timeout=30.0):
        """
        Safely set the magnet in Cartesian coords and wait until converged.
        """
        self.safeSetWait(
            set_func=self.set_field_cartesian,
            get_func=self.get_field_cartesian,
            target_values=(Bx, By, Bz),
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def safeWaitPolar(self, B, phi, theta, poll_interval=0.1, timeout=30.0):
        """
        Safely set the magnet in Polar coords and wait until converged (angle wrap-around aware).
        """
        def compare_func(current_values, target_values):
            return self.polar_compare_func(current_values, target_values, atol_B=3e-4, atol_angle=1)
        
        self.safeSetWait(
            set_func=self.set_field_polar,
            get_func=self.get_field_polar,
            target_values=(B, phi, theta),
            poll_interval=poll_interval,
            timeout=timeout,
            compare_func=compare_func
        )
