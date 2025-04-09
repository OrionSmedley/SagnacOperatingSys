import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from zhinst.ziPython import ziDAQServer

import pyvisa as pv

from pymeasure.instruments.newport import ESP300
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import modular_range_bidirectional, truncated_range
try:
    import PyDAQmx as daqmx
except:
    pass
import numpy as np
from time import sleep
import time
import serial

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

    @handle_timeout("getting phi")
    def getPhi(self):
        self._phi = self.motion_inst.phi.position
        return self._phi

    phi = property(getPhi,setPhi)

    def setTheta(self, theta):
        theta = modular_range_bidirectional(theta,[-180.,180.])
        self.set_vector_field(self._field, self._phi, theta)
        self._theta = theta

    def getTheta(self):
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

class APS100:
    """
    Instrument class for the Attocube APS100 magnet power supply.
    Manages USB communication and provides methods to send commands and receive responses.
    """

    def __init__(self, port, baudrate=9600, timeout=2):
        """
        Initialize the APS100 connection.

        Args:
            port (str): The USB port (e.g., COM3, /dev/ttyUSB0).
            baudrate (int): Communication baud rate (default: 9600).
            timeout (float): Timeout for read operations in seconds (default: 2).
        """
        # if self.connection and self.connection.is_open:
        #     self.disconnect()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None

    def connect(self):
        """
        Open the serial connection to the APS100.
        """
        if self.connection and self.connection.is_open:
            print(f"connection is already open on {self.port}")
            self.disconnect()
        try:
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Connected to APS100 on {self.port}")
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to APS100 on {self.port}: {e}")

    def disconnect(self):
        """
        Close the serial connection.
        """
        if self.connection:
            self.connection.close()
        print("Disconnected from APS100")

    def send_command(self, command):
        """
        Send a command to the APS100.

        Args:
            command (str): The command string to send (without newline).

        Returns:
            str: The response from the device.
        """
        if not self.connection or not self.connection.is_open:
            raise ConnectionError("Connection to APS100 is not open.")

        try:
            # Send command (append newline for termination)
            full_command = command + "\n"
            self.connection.write(full_command.encode('utf-8'))
            # print(f"Sent: {command}")

            # Read response
            time.sleep(1)  # Wait briefly for the device to respond
            response = self.connection.read(self.connection.in_waiting or 1)  # Read available data
            res = response.decode('utf-8').strip().split('\n', 1)[-1]
            return res

        except Exception as e:
            raise IOError(f"Failed to send command '{command}': {e}")

    def query_status(self):
        """
        Query the status of the APS100.

        Returns:
            str: Status information from the device.
        """
        return self.send_command("STATUS")

    def set_channel(self, channel):
        self.send_command(f'CHAN {int(channel)}')
        res = self.send_command('CHAN?')
        return res

    def get_field(self):
        res = self.send_command('IMAG?')
        value = float(res.replace('kG', ''))
        return value

    def set_field(self, field):
        # field in kG
        if abs(field) > 10:
            field = np.sign()*10
        
        current_field = self.get_field()
        time.sleep(0.1)
        if field > current_field:
            self.send_command(f'ULIM {field}')
            time.sleep(0.1)
            self.send_command('SWEEP UP')
        elif field < current_field:
            self.send_command(f'LLIM {field}')
            time.sleep(0.1)
            self.send_command('SWEEP DOWN')
        else:
            pass

    def check_field(self, set_field, tol = 0.001):
        current_field = self.get_field()
        if abs(set_field - current_field) > tol:
            return False
        else:
            return True
    
    def zero_field(self):
        self.send_command('SWEEP ZERO')

class HF2LI(ziDAQServer):
    """This is the class for the Zurich HF2LI lockin amplifier"""
    def __init__(self, port, API_level, dev_num):
        super().__init__('localhost', port, API_level)
        self.dev = '/dev' + str(dev_num) + '/'
        self.dev_num = dev_num

    # Signal Inputs; Our model has 2; 0-indexed
    def get_range(self, sig):
        return self.getDouble(self.dev + 'sigins/' + str(sig) + '/range')
    def set_range(self, sig, x):
        self.setDouble(self.dev + 'sigins/' + str(sig) + '/range', x)

    def get_ac_coupling(self, sig):
        return self.getInt(self.dev + 'sigins/' + str(sig) + '/ac')
    def set_ac_coupling(self, sig, x):
        self.setInt(self.dev + 'sigins/' + str(sig) + '/ac', int(x))

    def get_imp50(self, sig):
        return self.getInt(self.dev + 'sigins/' + str(sig) + '/imp50')
    def set_imp50(self, sig, x):
        self.setInt(self.dev + 'sigins/' + str(sig) + '/imp50', int(x))

    def get_differential_mode(self, sig):
        return self.getInt(self.dev + 'sigins/' + str(sig) + '/diff')
    def set_differential_mode(self, sig, x):
        self.setInt(self.dev + 'sigins/'+ str(sig) + '/diff', int(x))

    # Oscillators; Our model has 6; 0-indexed
    def get_osc_freq(self, osc_num):
        return self.getDouble(self.dev + 'oscs/' + str(osc_num) + '/freq')
    def set_osc_freq(self, osc_num, x):
        self.setDouble(self.dev + 'oscs/'+ str(osc_num) + '/freq', x)

    # Demodulators
    def get_osc_select(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/oscselect')
    def set_osc_select(self, demod_num, osc_num):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/oscselect', int(osc_num))

    def get_harmonic(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/harmonic')
    def set_harmonic(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/harmonic', int(x))

    def get_phase(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/phaseshift')
    def set_phase(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/phaseshift', x)

    def get_input(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/adcselect')
    def set_input(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/adcselect', x)

    def get_filter_order(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/order')
    def set_filter_order(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/order', x)

    def get_tc(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/timeconstant')
    def set_tc(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/timeconstant', x)

    def get_sinc(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/sinc')
    def set_sinc(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/sinc', x)

    def get_enable_demod(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/enable')
    def set_enable_demod(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/enable', x)

    def get_xferRate(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/rate')
    def set_xferRate(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/rate', x)

    # Output Amplitudes; a linear comb of up to 8 Sine outputs
    def get_vout(self, out_num, osc_num):
        return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num))
    def set_vout(self, out_num, osc_num, x):
        self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/amplitudes/' + str(osc_num), x)

    def get_enable_output(self, out_num, osc_num):
        return self.getInt(self.dev + 'sigouts/' + str(out_num) + '/enables/' + str(osc_num))
    def set_enable_output(self, out_num, osc_num, x):
        self.setInt(self.dev + 'sigouts/'+ str(out_num) + '/enables/' + str(osc_num), x)

    # Signal outputs
    def get_sigon(self, out_num):
        return self.getInt(self.dev + 'sigouts/' + str(out_num) + '/on')
    def set_sigon(self, out_num, x):
        self.setInt(self.dev + 'sigouts/'+ str(out_num) + '/on', x)

    def get_sigadd(self, out_num):
        return self.getInt(self.dev + 'sigouts/' + str(out_num) + '/add')
    def set_sigadd(self, out_num, x):
        self.setInt(self.dev + 'sigouts/'+ str(out_num) + '/add', x)

    def get_outrange(self, out_num):
        return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/range')
    def set_outrange(self, out_num, x):
        self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/range', x)

    def get_offset(self, out_num):
        return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/offset')
    def set_offset(self, out_num, x):
        self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/offset', x)


    # Data Collection
    def sample(self, demod_num):
        return self.getSample(self.dev + 'demods/' + str(demod_num) + '/sample')

    def sub(self, demod_num):
        self.subscribe(self.dev + 'demods/' + str(demod_num) + '/sample')

    def poll_and_unpack(self, poll_time, poll_timeout, demod_nums, data_keys, ratio=True, average = True):
        if not isinstance(demod_nums, list):
            demod_nums = [demod_nums]
        if not isinstance(data_keys, list):
            data_keys = [data_keys]
        dat = self.poll(poll_time,poll_timeout)['dev' + str(self.dev_num)]['demods']
        return_dict = {d:{} for d in demod_nums}
        for d in demod_nums:
            for k in data_keys:
                while True:
                    try:
                        if average:
                            return_dict[d][k] = float(np.mean(dat[str(d)]['sample'][k]))
                        else:
                            return_dict[d][k] = dat[str(d)]['sample'][k]
                    except:
                        sleep(poll_time)
                        dat = self.poll(poll_time,poll_timeout)['dev' + str(self.dev_num)]['demods']
                    else:
                        break
        if ratio and average:
            return_dict['ratio'] = float(np.mean(dat['0']['sample']['x']/dat['1']['sample']['y']))
        if ratio and not average:
            return_dict['ratio'] = dat['0']['sample']['x']/dat['1']['sample']['y']
        return return_dict



    def shutdown(self):
        log.info("Shutting down Zurich Lock-in")
        self.set_sigon(0,0)
        self.set_sigon(1,0)
        log.info("Done shutting down Lock-in")
        # self.isShutdown = True

