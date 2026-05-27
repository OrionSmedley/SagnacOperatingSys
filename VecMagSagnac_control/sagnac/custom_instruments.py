from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa
from .instruments.AMI420 import AMI420
# from sagnac.instruments import APS100 # Uses USB virtual com ports, slower and less accurate
from sagnac.instruments.aps100GPIB import APS100 # Uses GPIB ports

import atto_device.CRYO2100 as cr


def handle_timeout(fail_mode):
    def handle_timeout_decorator(func):
        def func_wrapper(self, *args, **kwargs):
            esp_faliure_counter = 0
            esp_success = False
            FALIURE_LIMIT = 50
            while esp_faliure_counter < FALIURE_LIMIT:
                try:
                    return func(self, *args, **kwargs)
                except pyvisa.errors.VisaIOError:
                    esp_faliure_counter += 1
                    log.warning("failed {mode}, at count {count} of {max}".format(
                        mode=fail_mode,
                        count=esp_faliure_counter,
                        max=FALIURE_LIMIT
                        )
                    )
                    log.info("Clearing GPIB connection %s"%self.name)
                    self.adapter.manager.visalib.clear(self.adapter.connection.session)
                    continue
                esp_success = True # only runs if we beat try statement
                break
            if not esp_success:
                raise RuntimeError("Not able to successfully communicate with magnet")
        return func_wrapper
    return handle_timeout_decorator

# NOTE: magnet is controlled with field

class vectorMagnetBase(AMI420):
    """This is the meta class for messing with a single axis of the vector
    magnet in H8"""

    DELAY = 0.05

    def __init__(self, resourceName, coil_constant, current_limit, axis, field_ramp_rate=0, stability=0, **kwargs):
        """Setting up power supply/controller parameters and setting to remote
        mode"""
        delay = 0.05
        super().__init__(resourceName, **kwargs)
        self.name = "Vector Magnet Vertical Z Axis"

        #Using SI units for Voltage, current, field and ramp rate
        self.field_units = 'tesla'
        self.ramp_rate_units ='seconds'

        print('set units')
        sleep(delay)

        #Setting the min, max output paramters for AMI4Q05100PS
        self.current_minimum = -100
        self.current_maximum = 100
        self.voltage_maximum = 5
        self.voltage_minimum = -5

        print('set current voltage max min')
        sleep(delay)

        #Stability setting should be close to zero when magnet is connected to
        #circuit. If testing the supplies without magnet, use 100%
        #self.stability = stability

        #print('set stability')
        #sleep(delay)

        #Value taken from Manual, also referred to as field to current ratio
        self.coil_constant = coil_constant #Telsa/Amp

        print('set coil constant')
        sleep(delay)

        #Setting the max current to attain a max field of 6.045705 T,
        #~1T less than the maximum rated field
        self.magnet_current_limit = current_limit #Amps

        print('set current limit')
        sleep(delay)

        #Fixing the ramp rate, calculated assuming L=7.8 Henries
        #Max ramp rate = 0.0861 T/sec for max 5V from power supply
        #Setting it to be 0.043 T/sec which corresponds to 320mA/sec which is
        #within ramp rate range for AMI420
        #self.field_ramp_rate = field_ramp_rate #T/sec CHANGED FROM 0.043 T/sec

        #print('set field ramp rate')
        #sleep(delay)

        #What does this do?
        self.auto_quench_detect = True

        print('set auto quench detect')
        sleep(delay)

        #Calculating the field limits given the coil constant and magnet
        #current limit
        field_limit = self.coil_constant*self.magnet_current_limit

        print('read successfully')
        self._fieldlims = [-1*field_limit, field_limit]

        print('set field limits and done')
        self.axis = axis

    """This function sets the field to given setpoint"""
    @handle_timeout("setting field")
    def setField(self, nfield):
        if (nfield < self._fieldlims[0] or nfield > self._fieldlims[1]):
            log.warning(f"""Field setpoint of {nfield} is too high for {self.axis} magnet.
                        Staying at previous setpoint""")
            log.info("%s" %self.state)

        else:
            self.set_ramp_mode()
            self.field_setpoint = nfield

    """Reads the field in the magnet coils"""
    @handle_timeout("getting field")
    def getField(self):
        return self.magnet_field

    field = property(getField, setField)

    """Reads the magnet voltage"""
    @handle_timeout("getting voltage")
    def getMagVoltage(self):
        return self.magnet_voltage

    @handle_timeout("ramping")
    def is_ramping(self):
        try:
            return self.state == 'Ramping'
        except ValueError:
            # with open(r'C:\Users\Ralph Group\Documents\Data\weird_error_log.txt', 'a') as f:
            #     f.write("Failed at STATE?\n")
            #     f.write('STATE read is: '+self.adapter.connection.ask('STATE?')+'\n')
            #     f.write('IDN read is: '+self.adapter.connection.ask('*IDN?')+'\n\n')
            raise ValueError("Bad return from state")

    @handle_timeout("holding")
    def is_holding(self):
        return self.state == 'Holding'

    @handle_timeout("zeroing")
    def is_zeroing(self):
        return self.state == 'Zeroing'

    @handle_timeout("Quench detected")
    def is_quenched(self):
        return self.state == 'Quench'

    @handle_timeout("Paused")
    def is_paused(self):
        return self.state == 'Paused'

    # brings current to zero and ensures in local mode
    @handle_timeout("Shutdown")
    def shutdown(self):
        """ Ensures the magnet is set to zero field """
        super().shutdown()
        log.info("Shutting down the %s magnet"%self.axis)
        self.field = 0. # turn field off
        sleep(0.1)
        self.local() #Can this be done manually from frontpanel?

class vectorMagnetZ(vectorMagnetBase):
    """
    The z component of the vector magnet
    """

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            coil_constant = 0.134349, #T/A
            current_limit = 45, # A TODO check, is =6T
            stability=50, # %, does nothing for now
            field_ramp_rate=0.0043, # T/s, does nothing for now
            axis = 'Z',
            **kwargs
        )
        self.name = "Vector Magnet Z Axis"

class vectorMagnetX(vectorMagnetBase):
    """
    The x component of the vector magnet
    """

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            coil_constant = 0.018891, #T/A TODO: check
            current_limit = 48, # A TODO check, is =0.9T
            stability = 0, # %, does nothing for now
            field_ramp_rate = 0.0043, # T/s, does nothing for now
            axis = 'X',
            **kwargs
        )
        self.name = "Vector Magnet X Axis"

class vectorMagnetY(vectorMagnetBase):
    """
    The y component of the vector magnet
    """

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            coil_constant = 0.018891, #T/A TODO: check
            current_limit = 48, # A TODO check, is =0.9T
            stability = 0, # %, does nothing for now
            field_ramp_rate = 0.0043, # T/s, does nothing for now
            axis='Y',
            **kwargs
        )
        self.name = "Vector Magnet Y Axis"

class vectorMagnetFull:
    """
    Class to control all three axes of the vector magnet simultaneously.
    Uses the usual physics parameterization of the magnetic field.
    """

    def __init__(self, device):
        self.device = device
        self.device.connect()
        # self.magnet_x = 2
        # self.magnet_y = 1
        # self.magnet_z = 0

        # self._x_field = self.magnet_x.field
        # self._y_field = self.magnet_y.field
        # self._z_field = self.magnet_z.field

        # limit such that below this field change the magnet does not actually change field,
        # to limit commands sent to the magnet
        self._field_difference_cutoff = 0 #1e-5 # 0.1 G

        # TODO: should we reset the current limit of the z magnet or just
        # trust that the checking in this class will always be OK?

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

        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim: #np.sqrt returns positive square root
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

        if np.isclose(Bx_set,Bx_current, atol=ATOL) and np.isclose(By_set,By_current,atol=ATOL) and np.isclose(Bz_set, Bz_current, atol=ATOL):
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

        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim: #np.sqrt returns positive square root
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

        if np.isclose(Bx_set,Bx_current, atol=ATOL) and np.isclose(By_set,By_current,atol=ATOL) and np.isclose(Bz_set, Bz_current, atol=ATOL):
            # log.info("Field is not close to the setpoint")
            log.info("field is close to the setpoint")
            return True
        else:
            log.info(f"{Bx_current}, {By_current}, {Bz_current}")
            return False

    def is_ramping(self):
        # what is getFieldControl?--x
        return self.device.magnet.getFieldControl(0)

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
        # self.magnet_x.shutdown()
        # self.magnet_y.shutdown()
        # self.magnet_z.shutdown()
        self.device.action.shutdown()

    def set_magnet_field(self, magnet, setPoint):
        # magnet is 0, 1, 2
        # field strength
        # I wrote this for self.z_magnet.field = self.saturating_field in heterodyneProcedure
        self.device.magnet.setHSetPoint(magnet, setPoint)

class Keithley220(Instrument):
    """ Represents a Keithley 220 programmable current source """

    current = Instrument.setting(
        "I%gX", """ Sets the current in Amps """,
        validator = truncated_range,
        values = [-0.101,0.101]
        )

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            "Keithley 220 Programmable Current Source",
            **kwargs
        )

    def enable(self):
        """ Enables output """
        self.write('F1X')

    def disable(self):
        """ Disables output """
        self.write('F0X')

    def shutdown(self):
        """ Sets current to zero and disables the instrument """
        super().shutdown()
        self.current = 0.
        self.disable()

class APS100_(Instrument):
    """ Represents a Attocube APS100 programmable magnet power supply """

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            "Keithley 220 Programmable Current Source",
            **kwargs
        )

    current = Instrument.control(
        "IMAG?", "IMAG %g",
        """ A floating point property that represents the current
        in Amps. This property can be set. """,
        validator=truncated_range,
        values=[-1,1]
    )

    def shutdown(self):
        """ Sets current to zero and disables the instrument """
        super().shutdown()
        self.current = 0.
        self.disable()

class vectorMagnetFullUSB:
    """
    Class to control all three axes of the vector magnet simultaneously.
    Uses the usual physics parameterization of the magnetic field.
    """
    Tthresh = 4.2
    ATOL = 1e-3
    def __init__(self, limit = 9.9):
        # in this case device = APS100("port")
        self.device_x = APS100(1) # Uses GPIB ports
        self.device_2 = APS100(3) # Uses GPIB ports

        # self.device_x = APS100("COM4") # Uses USB virtual com ports, slower and less accurate
        # self.device_2 = APS100("COM5") # Uses USB virtual com ports, slower and less accurate
        # device 2 channel 1 is Z
        # device 2 channel 2 is Y

        # limit such that below this field change the magnet does not actually change field,
        # to limit commands sent to the magnet
        self._field_difference_cutoff = 0 #1e-5 # 0.1 G

        # TODO: should we reset the current limit of the z magnet or just
        # trust that the checking in this class will always be OK?

        self._field_mag_lim = limit # set to 1? bootleg version is kG, previous auttodry gui was T

        self._B_sign = 1

        self.atto = cr("192.168.1.1")
        self.atto.connect()
        # self.Bx_set, self.By_set, self.Bz_set = self.get_field_cartesian()
        # self.B_set, self.phi_set, self.theta_set = self.get_field_polar()

    def connect(self):
        self.device_x.disconnect()
        self.device_2.disconnect()
        self.device_x.connect()
        self.device_x.write("REMOTE")
        self.device_2.connect()
        self.device_2.write("REMOTE")
        Bx, By, Bz = self.get_field_cartesian()
        print( "conecting. The field is", np.sqrt(Bx*Bx + By*By + Bz*Bz))
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            self.device_x.disconnect()
            self.device_2.disconnect()
            print( "Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
            raise ValueError("Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
    
    def setSafe_wait_cart(self, bx,by,bz):
        temp = self.atto.condenser.getTemperature()
        if temp > self.Tthresh:
            # atto.disconnect() 
            print( f"yikes, resevoir at {temp}C > max {self.Tthresh}")
            self.shutdown()
            raise RuntimeError(f"shut down bc resevoir at {temp}C > max {self.Tthresh}")

        tic = time()
        Bx_init, By_init, Bz_init = self.get_field_cartesian()
        # print(f"Bz initial: {Bx_init, By_init, Bz_init}")
        if not np.abs(bz) > np.abs(Bz_init): 
            # print("entering if")
            while not self.check_field_cartesian(Bx_init, By_init, bz, 10*self.ATOL):
                print("waiting for z to ramp down")
                sleep(0.1)
                self.set_field_cartesian(Bx_init,By_init,bz)
                sleep(0.1)
                print(f"waiting for z to ramp down {time()-tic}")

        while not self.check_field_cartesian(bx, by, bz, self.ATOL):
            sleep(0.1)
            self.set_field_cartesian(bx,by,bz)
            sleep(0.1)
            print(f"waiting for mag for {time()-tic}")

        self.Bx_set = bx
        self.By_set = by
        self.Bz_set = bz
        self.B_set, self.phi_set, self.theta_set = self.get_field_polar()
    
    def setSafeWaitBx(self, b):
        self.setSafe_wait_cart(b, self.By_set, self.Bz_set)

    def setSafeWaitBy(self, b):
        self.setSafe_wait_cart(self.Bx_set, b, self.Bz_set)

    def setSafeWaitBz(self, b):
        self.setSafe_wait_cart(self.Bx_set, self.By_set, b)


    def setSafe_wait_polar(self, B,phi, theta): 
        temp = self.atto.condenser.getTemperature()
        if temp > self.Tthresh:
            # atto.disconnect() 
            print( f"yikes, resevoir at {temp}C > max {self.Tthresh}")
            self.shutdown()
            raise RuntimeError(f"shut down bc resevoir at {temp}C > max {self.Tthresh}")


        tic = time()
        
        while not self.check_field_polar(B,phi, theta,self. ATOL):
            sleep(0.1)
            self.set_field_polar(B,phi, theta)
            sleep(0.1)
            print(f"waiting for mag for {time()-tic}")

        self.B_set = B
        self.phi_set = phi
        self.theta_set = theta
        self.Bx_set, self.By_set, self.Bz_set = self.get_field_cartesian()
    
    
    def setSafeWaitB(self, b):
        self.setSafe_wait_polar(b, self.phi_set, self.theta_set)

    def setSafeWaitPhi(self, phi):
        self.setSafe_wait_polar(self.B_set, phi, self.theta_set)

    def setSafeWaitTheta(self, theta):
        self.setSafe_wait_polar(self.B_set, self.phi_set, theta)



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

        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim: #np.sqrt returns positive square root
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)

        if B < 0:
            self._B_sign = -1
        else:
            self._B_sign = 1
        # self.device.magnet.setHSetPoint3D(Bz, By, Bx)

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
        """Checks the current field value to make sure it is within absolute tolerance of setpoint"""
        phi = phi*np.pi/180
        theta = theta*np.pi/180

        Bx_set = np.round(B*np.cos(phi)*np.sin(theta), 5)
        By_set = np.round(B*np.sin(phi)*np.sin(theta), 5)
        Bz_set = np.round(B*np.cos(theta), 5)

        # Bz_current, By_current, Bx_current = self.device_z.get_field(), self.device_y.get_field(), self.device_x.get_field()
        self.device_2.set_channel(1) # z
        Bz_current = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By_current = self.device_2.get_field()
        Bx_current = self.device_x.get_field()

        if np.isclose(Bx_set,Bx_current, atol=ATOL) and np.isclose(By_set,By_current,atol=ATOL) and np.isclose(Bz_set, Bz_current, atol=ATOL):
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

    def is_ramping(self):
        # what is getFieldControl?--x
        # return self.device.magnet.getFieldControl(0)
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

class vectorMagnetFullUSB_highZ:
    """
    Class to control all three axes of the vector magnet simultaneously.
    Uses the usual physics parameterization of the magnetic field.
    """

    def __init__(self, limit = 90):
        self.device_x = APS100(1) # Uses GPIB ports
        self.device_2 = APS100(3) # Uses GPIB ports

        # self.device_x = APS100("COM4") # Uses USB virtual com ports, slower and less accurate
        # self.device_2 = APS100("COM5") # Uses USB virtual com ports, slower and less accurate
        # device 2 channel 1 is Z
        # device 2 channel 2 is Y
        self._field_difference_cutoff = 0 #1e-5 # 0.1 G
        self._field_mag_lim = limit # bootleg version is kG, previous auttodry gui was T
        # self._B_sign = 1 #Not sure what this is for. Delete? 2025/01/24 - Orion and Ethan

    def connect_highZ(self):
        self.device_x.disconnect()
        self.device_2.disconnect()
        self.device_x.connect()
        self.device_2.connect()
        self.device_x.write("REMOTE")
        self.device_2.write("REMOTE")
        
        BxCon,ByCon,BzCon = self.get_field_cartesian()
        
        if np.abs(BzCon) > 9.9:
            if np.abs(BxCon) >0 or np.abs(ByCon) > 0:
                self.device_x.disconnect()
                self.device_2.disconnect()
                print( "Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
                raise ValueError("Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
            else:
                print( "Not zeroing Bx and By, because if useful, you were already screwed.")
        else:
            print("Zeroing X magnet")
            self.device_x.zero_field()

            print("Zeroing Y magnet")
            self.device_2.set_channel(2)
            self.device_2.zero_field()


        print("disconnecting from x for safety")
        self.device_x.disconnect()
        self.device_2.set_channel(1)

    def set_field_highZ(self, Bz):
        log.info('Setting Bz to : %g'%(Bz))
        if np.abs(Bz) > self._field_mag_lim: #np.sqrt returns positive square root
            log.error("A large field of %g was requested"%Bz)
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)

        # #Not sure what this is for. Delete? 2025/01/24 - Orion and Ethan
        # if Bz < 0:
        #     self._B_sign = -1
        # else:
        #     self._B_sign = 1

        self.device_2.set_channel(1)
        self.device_2.set_field(Bz)

    def get_field_highZ(self):
        self.device_2.set_channel(1) # z
        Bz = self.device_2.get_field()
        return Bz


    def get_field_cartesian(self):
            """
            Returns the cartesian parameterization of the field in the order X, Y, Z.
            will throw error after class is connected.
            """
            # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
            self.device_2.set_channel(1) # z
            Bz = self.device_2.get_field()
            self.device_2.set_channel(2) # y
            By = self.device_2.get_field()
            Bx = self.device_x.get_field()
            return Bx, By, Bz

    def check_field_highZ(self, Bset, ATOL):
            """Checks the current field value to make sure it is within absolute tolerance of setpoint """
            # Bx_current = self.device.magnet.getH(2)
            # By_current = self.device.magnet.getH(1)
            # Bz_current = self.device.magnet.getH(0)
            Bz = self.get_field_highZ()

            print(f" currently Bz= {Bz}") #redundant, if you use the monkypatch for pymeasure

            if np.isclose(Bset, Bz, atol=ATOL):
                log.info("field is close to the setpoint")
                return True
            else:
                log.info(f" currently Bz= {Bz}")
                return False
            
    def shutdown(self):
        """
        Shuts down each of the magnets individually
        """
        log.info("Shutting down only the Z magnet")
        self.device_2.set_channel(1) # z
        self.device_2.zero_field()


        self.device_2.disconnect()
        try:
            self.device_x.disconnect()
        except:
            print("no device x to disconect")


