import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import pyvisa as pv
from ..aps100 import APS100

from pymeasure.instruments.newport import ESP300
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import modular_range_bidirectional, truncated_range
try:
    import PyDAQmx as daqmx
except:
    pass
import numpy as np
from time import sleep

# this function is to be used as a decorator, basically just wrapping whatever
# function it decorates in a try/except statement to catch timeout errors
def handle_timeout(fail_mode):
    def handle_timeout_decorator(func):
        def func_wrapper(*args, **kwargs):
            esp_faliure_counter = 0
            esp_success = False
            FALIURE_LIMIT = 10
            while esp_faliure_counter < FALIURE_LIMIT:
                try:
                    return func(*args, **kwargs)
                except pv.errors.VisaIOError:
                    esp_faliure_counter += 1
                    log.warning("failed {mode}, at count {count} of {max}".format(
                        mode=fail_mode,
                        count=esp_faliure_counter,
                        max=FALIURE_LIMIT
                        )
                    )
                    continue
                esp_success = True # only runs if we beat try statement
                break
            if not esp_success:
                raise RuntimeError("Not able to successfully communicate with ESP300")
        return func_wrapper
    return handle_timeout_decorator

class coilMagnet:
    """ This is the pseudo instrument class for the coil magnet and Kepco on the
    Sagnac station"""

    def setVolts(self, volts):
        """ Ramps B field to requested safely """
        now = self.volts
        if np.abs(volts) > 10:
            log.warning("%g Volts is too high for magnet! Setting to 10 V"%volts)
            volts = np.sign(volts)*10
        while abs(volts-now) > self._voltage_step:
            now += self._voltage_step*np.sign(volts-now)
            self._set_volts(now)
            sleep(self._delay)
        self._set_volts(volts)

    def getVolts(self):
        # create task and set up channel
        self._daq_interface = daqmx.Task()
        self._daq_interface.CreateAIVoltageChan(self.device_read_str.encode(),"",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
        self._daq_interface.StartTask()
        # write field
        read_volts = daqmx.float64()
        self._daq_interface.ReadAnalogScalarF64(10.0,read_volts,None) # args: timeout, ctypes thing result is read to, "reserved" (always None)
        self._daq_interface.StopTask()
        self._daq_interface.ClearTask()
        return read_volts.value

    volts = property(getVolts,setVolts)

    def setField(self, B):
        self.volts = self.B2V(B)

    def getField(self):
        return self.V2B(self.volts)

    field = property(getField,setField)

    @handle_timeout("initializing")
    def __init__(self, powerAdapter, **kwargs):

        # set up DAQ interface
        self.name = "Coil Magnet"
        self._daq_interface = None
        self.device_write_str = '/' + powerAdapter.resource_name + '/' + powerAdapter.channels[0]
        self.device_read_str = '/' + powerAdapter.resource_name + '/' + powerAdapter.channels[1]

        # set internal parameters
        # NOTE: as configured, takes 5 seconds to go from off to full power
        self._voltage_step = 0.01
        self._delay = 0.005 # time (s) to wait for voltage to change by voltage_step
        self._field = 0.
        self._voltagelims = [-10.,10.] # probably OK since we're always doing DAQ

    def _set_volts(self, volts):
        # create task and set up channel
        self._daq_interface = daqmx.Task()
        self._daq_interface.CreateAOVoltageChan(self.device_write_str.encode(),"",-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
        self._daq_interface.StartTask()
        # write the voltage and clear task
        self._daq_interface.WriteAnalogScalarF64(1,10.0,volts,None)
        self._daq_interface.StopTask()
        self._daq_interface.ClearTask()

    def B2V(self, B):
        return B/(40*1e-4)
    def V2B(self, V):
        return V*(40*1e-4)

class daedalusProjField:
    """This is the pseudo instrument class for the projected field magnet in the
    Daedalus station."""

    def setVolts(self, volts):
        """ Ramps B field to requested safely """
        now = self.volts
        if np.abs(volts) > 10:
            log.warning("%g Volts is too high for magnet! Setting to 10 V"%volts)
            volts = np.sign(volts)*10
        while abs(volts-now) > self._voltage_step:
            now += self._voltage_step*np.sign(volts-now)
            self._set_volts(now)
            sleep(self._delay)
        self._set_volts(volts)
        self.wait_for_operation()

    def getVolts(self):
        # create task and set up channel
        self._daq_interface = daqmx.Task()
        self._daq_interface.CreateAIVoltageChan(self.device_read_str.encode(),"",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
        self._daq_interface.StartTask()
        # write field
        read_volts = daqmx.float64()
        self._daq_interface.ReadAnalogScalarF64(10.0,read_volts,None) # args: timeout, ctypes thing result is read to, "reserved" (always None)
        self._daq_interface.StopTask()
        self._daq_interface.ClearTask()
        return read_volts.value

    volts = property(getVolts,setVolts)

    def setPhi(self, phi):
        # phi = modular_range_bidirectional(phi,[-170.,170.])
        self.set_vector_field(self._field, phi, self._theta)
        self._phi = phi
        self.wait_for_operation()

    @handle_timeout("getting phi")
    def getPhi(self):
        self._phi = self.motion_inst.phi.position
        return self._phi

    phi = property(getPhi,setPhi)

    def setTheta(self, theta):
        theta = modular_range_bidirectional(theta,[-180.,180.])
        self.set_vector_field(self._field, self._phi, theta)
        self._theta = theta
        self.wait_for_operation()

    def getTheta(self):
        return self._theta

    theta = property(getTheta,setTheta)

    def setField(self, field):
        self.set_vector_field(field, self._phi, self._theta)
        self._field = field
        self.wait_for_operation()

    def getField(self):
        return self._field # Can maybe make this better by inverting calibrations but w/e

    field = property(getField,setField)

    @property
    @handle_timeout("reading motion status")
    def in_motion(self):
        return not (self.motion_inst.phi.motion_done and
                    self.motion_inst.x.motion_done and
                    self.motion_inst.y.motion_done)

    @property
    @handle_timeout("reading errors")
    def errors(self):
        return self.motion_inst.errors

    @handle_timeout("initializing")
    def __init__(self, powerAdapter, motionAdapter, **kwargs):

        # set up DAQ interface
        self.name = "Projected Field Magnet"
        self._daq_interface = None
        self.device_write_str = '/' + powerAdapter.resource_name + '/' + powerAdapter.channels[0]
        self.device_read_str = '/' + powerAdapter.resource_name + '/' + powerAdapter.channels[1]

        # Connect Newport motion controller
        self.motion_inst = ESP300(motionAdapter)

        self.motion_inst.enable()

        self.motion_inst.y.units = 'millimeter'
        self.motion_inst.x.units = 'millimeter'
        self.motion_inst.phi.units = 'degree'
        # self._xlims = [self.motion_inst.x.left_limit,self.motion_inst.x.right_limit]
        # self._ylims = [self.motion_inst.y.left_limit,self.motion_inst.y.right_limit]
        self._philims = [self.motion_inst.phi.left_limit,self.motion_inst.phi.right_limit]

        # dummy parameters, to load from calibration
        self.centerX = 20.98 # can load from calibration, but probably won't be changing soon.
        self.centerY = 21.98
        self.polar_neg_coeff = [0]
        self.polar_pos_coeff = [0]
        self.volt_correction_neg_coeff = [0]
        self.base_volt_neg_coeff = [0]
        self.base_volt_pos_coeff = [0]

        # set internal parameters
        # NOTE: as configured, takes 5 seconds to go from off to full power
        self._voltage_step = 0.01
        self._delay = 0.005 # time (s) to wait for voltage to change by voltage_step
        self._field = 0.

        self._x = self.motion_inst.x.position
        self._y = self.motion_inst.y.position
        self._phi = self.motion_inst.phi.position

        self._theta = 0.
        self._voltagelims = [-10.,10.] # probably OK since we're always doing DAQ

    def _set_volts(self, volts):
        # create task and set up channel
        self._daq_interface = daqmx.Task()
        self._daq_interface.CreateAOVoltageChan(self.device_write_str.encode(),"",-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
        self._daq_interface.StartTask()
        # write the voltage and clear task
        self._daq_interface.WriteAnalogScalarF64(1,10.0,volts,None)
        self._daq_interface.StopTask()
        self._daq_interface.ClearTask()

    def load_calibration_params(self, calib_file_base):
        """
        Loads the calibration file, expected as csv's.
        Saves polynomials representing the calibration to attributes.
        """
        # NOTE: Use non-shimmed for usual measurements
        # NOTE: Since we're using polyval, the coefficient of the *highest* power is first
        # Center of the field
        self.centerX, self.centerY = np.loadtxt(calib_file_base + '_center_calib.csv', delimiter=',') # in mm
        # voltage to field relationship
        self.base_volt_coeff= np.loadtxt(calib_file_base + '_volt_center_calib.csv', delimiter=',')
        self.base_volt_calib = np.poly1d(self.base_volt_coeff)

        # polar angle to radial distance calibration
        self.radial_polar_coeff= np.loadtxt(calib_file_base + '_radial_polar_calib.csv', delimiter=',')
        self.radial_polar_calib = np.poly1d(self.radial_polar_coeff)

        # radial distance to voltage correction factor
        self.field_correction_coeff =  np.loadtxt(calib_file_base + '_fieldratio_calib.csv', delimiter=',')
        self.field_correction_calib = np.poly1d(self.field_correction_coeff)

    @handle_timeout("shutting down")
    def shutdown(self):
        """ Ensures the magnet is set to zero field """
        log.info("Shutting down %s." % self.name)
        self.set_vector_field(0.,0.,0.)
        self.wait_for_operation()

    def base_voltage_calibration(self, B):
        """Determines voltage needed to achieve B, assuming magnet is centered"""

        return (0 if B == 0 else self.base_volt_calib(B))

    def angle_calibration(self, theta, phi):
        """
        Determines x and y position we need to go to to get requested phi and theta of magnetic field
        """

        radial_dist = 0 if theta == 0 else self.radial_polar_calib(theta)

        xloc = -1*radial_dist*np.sin(phi*np.pi/180.) + self.centerX
        yloc = radial_dist*np.cos(phi*np.pi/180.) + self.centerY

        return xloc, yloc, radial_dist

    def strength_calibration(self, radial_dist, B):
        """Determines factor by which voltage must be divided to give correct strength at given
        distance from the center of the calibration.

        The idea of this is that we need to go some distance away from center to get a theta
        component of the field. But, the strength changes as we go away from the center.
        So, to get the right field strength, we also need to change the voltage supplied
        to the magnet. The thing retuned by this is used to divide the volts which we would
        usually give to the magnet to achieve the requested field if it were centered.
        """

        Bcorr = 1 if radial_dist==0 else self.field_correction_calib(radial_dist)

        return self.base_volt_calib(B/Bcorr)

    # TODO: have field set functions to ensure continuity when sweeping
    # field in certain ways, e.g. sweeping Bz with constant IP field

    @handle_timeout("setting field")
    def set_vector_field(self, B, phi=0., theta=0.):
        """ Uses calibrations to set a requested magnetic field vector at the
        marked location. Should only be used through setting given parameters. """
        x, y, r = self.angle_calibration(theta, phi)
        self.set_volts = self.strength_calibration(r, B)

        # only send command to newport if we actually need to move
        if not np.isclose(self._x, x, atol=1e-4):
            self.motion_inst.x.position = x
            self._x = x

        # only send command to newport if we actually need to move
        if not np.isclose(self._y, y, atol=1e-4):
            self.motion_inst.y.position = y
            self._y = y

        # only send command to newport if we actually need to move
        if not np.isclose(self._phi, phi, atol=1e-4):
            self.motion_inst.phi.position = phi # see phi setter function
            self._phi = phi

        if not (self._voltagelims[0] <= self.set_volts <= self._voltagelims[1]):
            self.set_volts = truncated_range(self.set_volts,self._voltagelims)
            log.warning('Magnet voltage overload! Magnet voltage being set to %g'%self.set_volts)
        self.volts = self.set_volts
        self.wait_for_operation()

        self._field = B
    
    @handle_timeout("setting field")
    def set_cart_vector_field(self, Bx, By, Bz):
        """ Uses calibrations to set a requested cartesian magnetic field vector at the
        marked location. Should only be used through setting given parameters. """
        theta = np.arctan2(Bz,np.sqrt(Bx**2 + By**2))*180./np.pi
        if Bx == 0 and By == 0:
            phi = self.phi
        else:
            phi = np.arctan2(By,Bx)*180./np.pi
        B = np.sqrt(Bx**2+By**2+Bz**2)

        while not np.isclose(self.phi, phi, atol=1e-3):
            self.phi = phi
            while self.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.errors:
                log.warning('%s'%err)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        self.theta = theta
        while self.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.errors:
            log.warning('%s'%err)
        self.set_vector_field(B, phi, theta)

    def get_cart_vector_field(self):
        B = self.field
        phi_deg = self.phi
        theta_deg = self.theta

        if B is None or phi_deg is None or theta_deg is None:
            logging.error("Magnetic field parameters (B, phi, theta) are not fully set.")
            return (0.0, 0.0, 0.0)

        phi_rad = np.deg2rad(phi_deg)
        theta_rad = np.deg2rad(theta_deg)

        Bx = B * np.cos(theta_rad) * np.cos(phi_rad)
        By = B * np.cos(theta_rad) * np.sin(phi_rad)
        Bz = B * np.sin(theta_rad)

        logging.debug(f"Converted field from spherical to Cartesian coordinates:")
        logging.debug(f"B = {B}, phi = {phi_deg}°, theta = {theta_deg}°")
        logging.debug(f"Bx = {Bx}, By = {By}, Bz = {Bz}")

        return (Bx, By, Bz)

    @property
    def Bx(self):
        return self.get_cart_vector_field()[0]

    @property
    def By(self):
        return self.get_cart_vector_field()[1]

    @property
    def Bz(self):
        return self.get_cart_vector_field()[2]

    def wait_for_operation(self):
        while self.in_motion:
            sleep(0.1)
        for err in self.errors:
            log.warning('%s'%err)
    

    
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

class senis3AxHallProbe:
    """
    Basic implementatoin of the senis 3 axis Hall probe attached to the
    Daedalus setup. Includes all necessary conversions. Note the strange
    coordinate system.
    """

    volt2tesla = 0.2
    rad2deg = 180./np.pi
    deg2rad = np.pi/180.

    @property
    def x_field(self):
        return self.measure_field(self.dev_x)

    @property
    def y_field(self):
        return self.measure_field(self.dev_y)

    @property
    def z_field(self):
        return self.measure_field(self.dev_z)

    @property
    def polar_field(self):
        # positive y is down, positive z is forward, positive x is right
        x = self.x_field
        y = self.y_field
        z = -1*self.z_field
        phi = self.rad2deg*np.arctan2(x,y)
        theta = 90.-self.rad2deg*np.arctan2(np.sqrt(x**2+y**2),z)
        r = np.sqrt(x**2+y**2+z**2)
        return np.array([r,phi,theta])

    @property
    def field(self):
        return np.array([self.x_field,self.y_field,self.z_field])

    def __init__(self, adapter):
        # expects a DAQmxAdapter class with three channels, [x, y, z] channels
        self.dev_x = '/' + adapter.resource_name + '/' + adapter.channels[0]
        self.dev_y = '/' + adapter.resource_name + '/' + adapter.channels[1]
        self.dev_z = '/' + adapter.resource_name + '/' + adapter.channels[2]

    def read_voltage(self, device):
        """
        Reads 10000 points from the device and returns the average of them.
        Sampling should happen super fast.
        """
        # create task and set up channel
        self._daq_interface = daqmx.Task()
        self._daq_interface.CreateAIVoltageChan(device.encode(),"",daqmx.DAQmx_Val_Diff,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
        self._daq_interface.StartTask()
        # read voltage
        read_volts = np.zeros((10000,),dtype=np.float64)
        read = daqmx.int32()
        # args: samples per channel, timeout, fill mode, array to fill, total array size, number samples read, "reserved"
        self._daq_interface.ReadAnalogF64(10000,10.0,daqmx.DAQmx_Val_GroupByChannel,read_volts,10000,daqmx.byref(read),None)
        self._daq_interface.StopTask()
        self._daq_interface.ClearTask()
        return read_volts.mean()

    def measure_field(self, device):
        volts = self.read_voltage(device)
        return self.volt2tesla*volts

class vectorMagnetFullUSB:
    """
    Class to control all three axes of the vector magnet simultaneously.
    Uses the usual physics parameterization of the magnetic field.
    """

    def __init__(self):
        # in this case device = APS100("port")

        self.device_x = APS100("COM4")
        self.device_2 = APS100("COM5")
        # if self.device_x.connection and self.device_x.connection.is_open:
        # self.device_x.disconnect()
        # if self.device_2.connection and self.device_2.connection.is_open:
        # self.device_2.disconnect()
        


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
