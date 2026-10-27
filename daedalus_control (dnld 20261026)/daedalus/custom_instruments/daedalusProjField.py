import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import pyvisa as pv

from pymeasure.instruments.newport import ESP300
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import modular_range_bidirectional, truncated_range
from daedalus.custom_instruments.dsp7265 import DSP7265
from pymeasure.instruments.yokogawa import Yokogawa7651
try:
    import nidaqmx as daqmx
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

class daedalusProjFieldBase:
    """
    This is the pseudo instrument class for the projected field magnet in the
    Daedalus station. Does not include magnet power instrument.
    """

    def setPhi(self, phi):
        phi = modular_range_bidirectional(phi,[-360.,360.])
        self.set_vector_field(self._field, phi, self._theta)
        self._phi = phi

    @handle_timeout("getting phi")
    def getPhi(self):
        self._phi = self.motion_inst.phi.position
        return self._phi

    phi = property(getPhi,setPhi)

    def setTheta(self, theta):
        theta = modular_range_bidirectional(theta,[-360.,360.])
        self.set_vector_field(self._field, self._phi, theta)
        self._theta = theta

    def getTheta(self): #this function as well as calling magnet._theta directly are always returning 0 for any set value of theta, B fields are changing correctly
        return self._theta

    theta = property(getTheta,setTheta)

    def setField(self, field):
        self.set_vector_field(field, self._phi, self._theta)
        self._field = field

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
    def __init__(self, motionAdapter, **kwargs):


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
        self.centerX = 12.25 # can load from calibration, but probably won't be changing soon.
        self.centerY = 13.54
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
        log.warning('TessT!!!. the change works run 2!!')
        return self.base_voltage_calibration(B/Bcorr)

    # TODO: have field set functions to ensure continuity when sweeping
    # field in certain ways, e.g. sweeping Bz with constant IP field

    @handle_timeout("setting field")
    def set_vector_field(self, B, phi=0., theta=0.):
        """ Uses calibrations to set a requested magnetic field vector at the
        marked location. Should only be used through setting given parameters. """
        x, y, r = self.angle_calibration(theta, phi)
        self._r = r
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

class daedalusProjFieldDAQ(daedalusProjFieldBase):
    """This is the pseudo instrument class for the projected field magnet in the
    Daedalus station, using an NI DAQ control the magnet power supply."""

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
        sleep(self._delay)
        self._set_volts(volts)

    def getVolts(self):
        with daqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(self.device_read_str, min_val=-10., max_val=10.)
            read_volts = task.read()
        return read_volts

    volts = property(getVolts, setVolts)

    @handle_timeout("initializing")
    def __init__(self, powerAdapter, motionAdapter, **kwargs):
        super().__init__(motionAdapter, **kwargs)
        # set up DAQ interface
        self.name = "Projected Field Magnet"
        self._daq_interface = None
        self.device_write_str = '/' + powerAdapter.resource_name + '/' + powerAdapter.channels[0]
        self.device_read_str = '/' + powerAdapter.resource_name + '/' + powerAdapter.channels[1]

    def _set_volts(self, volts):
        # create task and set up channel
        with daqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan(self.device_write_str, min_val=-10., max_val=10.)
            status = task.write(volts)

class daedalusProjFieldYokogawa(daedalusProjFieldBase):
    """This is the pseudo instrument class for the projected field magnet in the
    Daedalus station."""

    def setVolts(self, volts):
        """ Ramps B field to requested safely """
        if np.abs(volts) > 10:
            log.warning("%g Volts is too high for magnet! Setting to 10 V"%volts)
            volts = np.sign(volts)*10
            
        nsteps = max(int(np.abs(volts-self.vsource.source_voltage)/self._voltage_step),1)
        duration = nsteps*self._delay
        
        self.vsource.ramp_to_voltage(volts, nsteps, duration)

    def getVolts(self):
        return self.vsource.source_voltage

    volts = property(getVolts,setVolts)

    @handle_timeout("initializing")
    def __init__(self, powerAdapter, motionAdapter, **kwargs):
        super().__init__(motionAdapter, **kwargs)
        
        self.name = "Projected Field Magnet Yokogawa"
        self.vsource = Yokogawa7651(powerAdapter)
        self.vsource.apply_voltage(max_voltage=10.0)
        self.vsource.enable_source()

    def _set_volts(self, volts):
        # create task and set up channel
        self.vsource.source_voltage = volts

    def shutdown(self):
        super().shutdown()
        self.vsource.shutdown()