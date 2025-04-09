import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.agilent import Agilent8257D
from ..custom_instruments import daedalusProjField
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class Hall2HarmBase(Procedure):
    """
    Dummy procedure to define common parameters for 2nd harmonic Hall.
    """
    
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')
    
    delay = FloatParameter("Delay", units="s", default=0.5)

    sensitivity1 = FloatParameter("First Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant1 = FloatParameter("First Harmonic Lockin Time Constant", units="s", default=0.5)
    lockin_phase1 = FloatParameter("First Harmonic Lockin Phase Offset", units='deg', default=0)
    lockin_ac_gain1 = FloatParameter("First Harmonic Lockin AC Gain", units="dB", default=40.0)
    lockin_sense_mode1 = Parameter("First Harmonic Lockin Sense Mode")
    
    sensitivity2 = FloatParameter("Second Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant2 = FloatParameter("Second Harmonic Lockin Time Constant", units="s", default=0.5)
    lockin_phase2 = FloatParameter("Second Harmonic Lockin Phase Offset", units='deg', default=0)
    lockin_ac_gain2 = FloatParameter("Second Harmonic Lockin AC Gain", units="dB", default=40.0)
    lockin_sense_mode2 = Parameter("Second Harmonic Lockin Sense Mode")
    
    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)
    lockin_frequency = FloatParameter("Lockin Frequency", units="Hz", default=137.17)
    
    queued_time = Parameter('Time Queued')

    first = True
    last = True 
    
class Hall2HarmAngProcedure(Hall2HarmBase):
    """
    Procedure for taking second harmonic Hall Measurements sweeping azimuthal
    (in-plane) angle
    """

    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_azimuth_start = FloatParameter("Start Azimuthal Field", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Azimuthal Field", units="deg", default=0.1)
    field_azimuth_step = FloatParameter("Azimuthal Field Step", units="deg", default=0.05)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_azimuth_measured", "field_azimuth", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning(f'{err}')
        
        self.magnet.load_calibration_params(self.calib_file)
        
        log.info(f"setting magnet polar orientation to {self.field_polar} deg")
        self.magnet.theta = self.field_polar
        if self.first:
            voltage_pole_elim = np.sign(self.field_strength) * 10
            log.info(f"Setting magnet voltage to {voltage_pole_elim} V to eliminate pole remnants")
            self.magnet.volts = voltage_pole_elim
        log.info(f"setting magnet field strength to {self.field_strength} T")
        self.magnet.field = self.field_strength

        # Lockin measuring first harmonic
        self.lockin1 = DSP7265("GPIB::11") # "secondary" lockin
        self.lockin1.mode = 0 # Single Harmonic Mode
        self.lockin1.set_voltage_mode()
        if self.lockin_sense_mode1 == 'A':
            self.lockin1.setChannelAMode()
        elif self.lockin_sense_mode1 == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode1 == 'A-B':
            self.lockin1.setDifferentialMode()
        self.lockin1.time_constant = self.time_constant1
        self.lockin1.sensitivity = self.sensitivity1
        self.lockin1.harmonic = 1
        self.lockin1.phase = self.lockin_phase1
        self.lockin1.reference = 'external rear' # TODO: should this be settable?
        self.lockin1.gain = self.lockin_ac_gain1

        # Lockin measuring second harmonic and driving current
        self.lockin2 = DSP7265("GPIB::12") # "primary" lockin
        self.lockin2.mode = 0 # Single Harmonic Mode
        self.lockin2.set_voltage_mode()
        if self.lockin_sense_mode2 == 'A':
            self.lockin2.setChannelAMode()
        elif self.lockin_sense_mode2 == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode2 == 'A-B':
            self.lockin2.setDifferentialMode()
        self.lockin2.time_constant = self.time_constant2
        self.lockin2.sensitivity = self.sensitivity2
        self.lockin2.harmonic = 2
        self.lockin2.reference = 'internal'
        self.lockin2.phase = self.lockin_phase2
        self.lockin2.frequency = self.lockin_frequency
        log.info(f"Setting lockin voltage output to {self.applied_voltage} V")
        self.lockin2.voltage = self.applied_voltage
        self.lockin2.gain = self.lockin_ac_gain2

    def execute(self):
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end, self.field_azimuth_step)
        if self.field_azimuth_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_azimuth_end)

        num_progress = angles.size
        start_time = time()
        sleep(5)

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting azimuthal field angle to {angle} deg")
            self.magnet.phi = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x,
                "X2": self.lockin2.x,
                "Y1": self.lockin1.y,
                "Y2": self.lockin2.y,
                "field_azimuth_measured": self.magnet.phi,
                "field_azimuth": angle,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scan. Shutting down instruments.")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err) # this should work, want to invoke the string conversion of the error
            self.lockin1.shutdown()
            self.lockin2.shutdown()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)

class Hall2HarmPolarAngProcedure(Hall2HarmBase):
    """
    Procedure for taking second harmonic Hall Measurements sweeping polar
    (out-of-plane) angle.
    """
    field_azimuth = FloatParameter("Magnetic Field Azimuth Angle", units="deg", default=0.)

    field_polar_start = FloatParameter("Start Polar Field", units="deg", default=0.)
    field_polar_end = FloatParameter("End Polar Field", units="deg", default=0.1)
    field_polar_step = FloatParameter("Polar Field Step", units="deg", default=0.05)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_polar_measured", "field_polar", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        self.magnet.load_calibration_params(self.calib_file)
        
        log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} degrees")
        self.magnet.phi = self.field_azimuth
        if self.first:
            voltage_pole_elim = np.sign(self.field_strength) * 10
            log.info("Setting magnet voltage to {voltage_pole_elim} V to eliminate pole remnants")
            self.magnet.volts = voltage_pole_elim
        log.info(f"setting magnet field strength to {self.field_strength} T")
        self.magnet.field = self.field_strength

        # Lockin measuring first harmonic
        self.lockin1 = DSP7265("GPIB::11") # "secondary" lockin
        self.lockin1.mode = 0 # Single Harmonic Mode
        self.lockin1.set_voltage_mode()
        if self.lockin_sense_mode1 == 'A':
            self.lockin1.setChannelAMode()
        elif self.lockin_sense_mode1 == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode1 == 'A-B':
            self.lockin1.setDifferentialMode()
        self.lockin1.time_constant = self.time_constant1
        self.lockin1.sensitivity = self.sensitivity1
        self.lockin1.harmonic = 1
        self.lockin1.phase = self.lockin_phase1
        self.lockin1.reference = 'external rear' # TODO: should this be settable?
        self.lockin1.gain = self.lockin_ac_gain1

        # Lockin measuring second harmonic and driving current
        self.lockin2 = DSP7265("GPIB::12") # "primary" lockin
        self.lockin2.mode = 0 # Single Harmonic Mode
        self.lockin2.set_voltage_mode()
        if self.lockin_sense_mode2 == 'A':
            self.lockin2.setChannelAMode()
        elif self.lockin_sense_mode2 == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode2 == 'A-B':
            self.lockin2.setDifferentialMode()
        self.lockin2.time_constant = self.time_constant2
        self.lockin2.sensitivity = self.sensitivity2
        self.lockin2.harmonic = 2
        self.lockin2.reference = 'internal'
        self.lockin2.phase = self.lockin_phase2
        self.lockin2.frequency = self.lockin_frequency
        log.info(f"Setting lockin voltage output to {self.applied_voltage} V")
        self.lockin2.voltage = self.applied_voltage
        self.lockin2.gain = self.lockin_ac_gain2

    def execute(self):
        angles = np.arange(self.field_polar_start,
                           self.field_polar_end, self.field_polar_step)
        if self.field_polar_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_polar_end)

        num_progress = angles.size
        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting polar field angle to {angle} deg")
            self.magnet.theta = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x,
                "X2": self.lockin2.x,
                "Y1": self.lockin1.y,
                "Y2": self.lockin2.y,
                "field_polar_measured": self.magnet.theta,
                "field_polar": angle,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scan. Shutting down instruments.")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin1.shutdown()
            self.lockin2.shutdown()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)

class Hall2HarmFieldProcedure(Hall2HarmBase):
    """
    Procedure for taking second harmonic Hall Measurements with the Daedalus setup
    sweeping field strength
    """

    field_strength_start = FloatParameter("Field Strength", units="T", default=0.0)
    field_strength_end = FloatParameter("Final Field Strength", units="T", default=0.1)
    field_strength_step = FloatParameter("Field Strength Step", units="T", default=0.01)
    
    field_azimuth = FloatParameter("Magnetic Field Azimuth Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)
    
    field_swap = Parameter("Field Swap", default='None')
    
    # TODO: add possibility of constant Z field?
    
    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_strength", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)

        while not np.isclose(self.magnet.phi, self.field_azimuth, 1e-2):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} degrees")
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
                
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)       

       # Lockin measuring first harmonic
        self.lockin1 = DSP7265("GPIB::11") # "secondary" lockin
        self.lockin1.mode = 0 # Single Harmonic Mode
        self.lockin1.set_voltage_mode()
        if self.lockin_sense_mode1 == 'A':
            self.lockin1.setChannelAMode()
        elif self.lockin_sense_mode1 == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode1 == 'A-B':
            self.lockin1.setDifferentialMode()
        self.lockin1.time_constant = self.time_constant1
        self.lockin1.sensitivity = self.sensitivity1
        self.lockin1.harmonic = 1
        self.lockin1.phase = self.lockin_phase1
        self.lockin1.reference = 'external rear'
        self.lockin1.gain = self.lockin_ac_gain1

        # Lockin measuring second harmonic and driving current
        self.lockin2 = DSP7265("GPIB::12") # "primary" lockin
        self.lockin2.mode = 0 # Single Harmonic Mode
        self.lockin2.set_voltage_mode()
        if self.lockin_sense_mode2 == 'A':
            self.lockin2.setChannelAMode()
        elif self.lockin_sense_mode2 == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode2 == 'A-B':
            self.lockin2.setDifferentialMode()
        self.lockin2.time_constant = self.time_constant2
        self.lockin2.sensitivity = self.sensitivity2
        self.lockin2.harmonic = 2
        self.lockin2.reference = 'internal'
        self.lockin2.phase = self.lockin_phase2
        self.lockin2.frequency = self.lockin_frequency
        log.info(f"Setting lockin voltage output to {self.applied_voltage} V")
        self.lockin2.voltage = self.applied_voltage
        self.lockin2.gain = self.lockin_ac_gain2

    def execute(self):
        # Make array of all field points to visit
        field_points = np.arange(self.field_strength_start,
                                    self.field_strength_end,
                                    self.field_strength_step)
        if self.field_strength_end not in field_points:
            field_points = np.append(field_points,self.field_strength_end)
        field_points = field_points[::-1] # reduce pole remnants
        
        if self.field_swap == 'None':
            pass
        elif self.field_swap == 'Hysteretic':
            field_points = np.concatenate((field_points,-1*field_points[::-1]))
            field_points = np.concatenate((-1*field_points, field_points))
        elif self.field_swap == 'Maximum':
            field_points = np.concatenate((field_points, -1*field_points))
        
        num_progress = field_points.size

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting magnetic field to {field} T")
            self.magnet.field = field
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x,
                "X2": self.lockin2.x,
                "Y1": self.lockin1.y,
                "Y2": self.lockin2.y,
                "field_strength": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin1.shutdown()
            self.lockin2.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class Hall2DualHarmBase(Procedure):
    """
    Dummy procedure to define common parameters for 2nd harmonic Hall.
    """
    
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')
    
    delay = FloatParameter("Delay", units="s", default=0.5)

    sensitivity1 = FloatParameter("First Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant1 = FloatParameter("First Harmonic Lockin Time Constant", units="s", default=0.5)
    lockin_phase1 = FloatParameter("First Harmonic Lockin Phase Offset", units='deg', default=0)

    sensitivity2 = FloatParameter("Second Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant2 = FloatParameter("Second Harmonic Lockin Time Constant", units="s", default=0.5)
    lockin_phase2 = FloatParameter("Second Harmonic Lockin Phase Offset", units='deg', default=0)
    
    lockin_ac_gain = FloatParameter("Lockin AC Gain", units="dB", default=40.0)
    lockin_sense_mode = Parameter("Lockin Sense Mode")
    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)
    lockin_frequency = FloatParameter("Lockin Frequency", units="Hz", default=137.17)
    
    queued_time = Parameter('Time Queued')

    first = True
    last = True 

class Hall2DualHarmAngProcedure(Hall2DualHarmBase):
    """
    Procedure for taking second harmonic Hall Measurements
    sweeping azimuthal (in-plane) angle using Dual harmonic mode (one lockin)
    """
    
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_azimuth_start = FloatParameter("Start Azimuthal Field", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Azimuthal Field", units="deg", default=0.1)
    field_azimuth_step = FloatParameter("Azimuthal Field Step", units="deg", default=0.05)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_azimuth_measured", "field_azimuth", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        self.magnet.load_calibration_params(self.calib_file)
        
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        if self.first:
            voltage_pole_elim = np.sign(self.field_strength) * 10
            log.info(f"Setting magnet voltage to {voltage_pole_elim} V to eliminate pole remnants")
            self.magnet.volts = voltage_pole_elim
        log.info(f"setting magnet field strength to {self.field_strength} T")
        self.magnet.field = self.field_strength

        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.set_voltage_mode()

        self.lockin.mode = 1 # Dual Harmonic Mode
        self.lockin.harmonic1 = 1
        self.lockin.harmonic2 = 2
        self.lockin.phase1 = self.lockin_phase1
        self.lockin.phase2 = self.lockin_phase2
        self.lockin.sensitivity1 = self.sensitivity1
        self.lockin.sensitivity2 = self.sensitivity2
        self.lockin.time_constant1 = self.time_constant1
        self.lockin.time_constant2 = self.time_constant2

        log.info(f"Setting lockin voltage output to {self.applied_voltage} V")
        self.lockin.voltage = self.applied_voltage
        self.lockin.frequency = self.lockin_frequency
        self.lockin.reference = 'internal'
        self.lockin.gain = self.lockin_ac_gain

        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()

    def execute(self):
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end, self.field_azimuth_step)
        if self.field_azimuth_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_azimuth_end)

        num_progress = angles.size
        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting azimuthal field angle to {angle} deg")
            self.magnet.phi = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "X2": self.lockin.x2,
                "Y1": self.lockin.y1,
                "Y2": self.lockin.y2,
                "field_azimuth_measured": self.magnet.phi,
                "field_azimuth": angle,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scan. Shutting down instruments.")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err) # this should work, want to invoke the string conversion of the error
            self.lockin.shutdown()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)

class Hall2DualHarmPolarAngProcedure(Hall2DualHarmBase):
    """
    Procedure for taking second harmonic Hall Measurements
    sweeping polar (out-of-plane) angle using Dual harmonic mode (one lockin)
    """

    field_azimuth = FloatParameter("Magnetic Field Azimuth Angle", units="deg", default=0.)

    field_polar_start = FloatParameter("Start Polar Field", units="deg", default=0.)
    field_polar_end = FloatParameter("End Polar Field", units="deg", default=0.1)
    field_polar_step = FloatParameter("Polar Field Step", units="deg", default=0.05)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_polar_measured", "field_polar", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        self.magnet.load_calibration_params(self.calib_file)
        
        log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} degrees")
        self.magnet.phi = self.field_azimuth
        if self.first:
            voltage_pole_elim = np.sign(self.field_strength) * 10
            log.info(f"Setting magnet voltage to {voltage_pole_elim} V to eliminate pole remnants")
            self.magnet.volts = voltage_pole_elim
        log.info(f"setting magnet field strength to {self.field_strength} T")
        self.magnet.field = self.field_strength

       # Lockin measuring harmonics
        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.set_voltage_mode()

        self.lockin.mode = 1 # Dual Harmonic Mode
        self.lockin.harmonic1 = 1
        self.lockin.harmonic2 = 2
        self.lockin.phase1 = self.lockin_phase1
        self.lockin.phase2 = self.lockin_phase2
        self.lockin.sensitivity1 = self.sensitivity1
        self.lockin.sensitivity2 = self.sensitivity2
        self.lockin.time_constant1 = self.time_constant1
        self.lockin.time_constant2 = self.time_constant2

        log.info(f"Setting lockin voltage output to {self.applied_voltage} V")
        self.lockin.voltage = self.applied_voltage
        self.lockin.frequency = self.lockin_frequency
        self.lockin.reference = 'internal'

        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()

    def execute(self):
        angles = np.arange(self.field_polar_start,
                           self.field_polar_end, self.field_polar_step)
        if self.field_polar_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_polar_end)

        num_progress = angles.size
        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting polar field angle to {angle} deg")
            self.magnet.theta = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "X2": self.lockin.x2,
                "Y1": self.lockin.y1,
                "Y2": self.lockin.y1,
                "field_polar_measured": self.magnet.theta,
                "field_polar": angle,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scan. Shutting down instruments.")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err) # this should work, want to invoke the string conversion of the error
            self.lockin.shutdown()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)

class Hall2DualHarmFieldProcedure(Hall2DualHarmBase):
    """
    Procedure for taking second harmonic Hall Measurements
    sweeping field strength using Dual harmonic mode (one lockin)
    """

    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)
    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)


    field_strength_start = FloatParameter("Field Strength", units="T", default=0.0)
    field_strength_end = FloatParameter("Final Field Strength", units="T", default=0.1)
    field_strength_step = FloatParameter("Field Strength Step", units="T", default=0.01)
    
    field_swap = Parameter("Field Swap")

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_strength", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)

        while not np.isclose(self.magnet.phi, self.field_azimuth, 1e-2):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} degrees")
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
                
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)  

      # Lockin measuring harmonics
        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.set_voltage_mode()
        self.lockin.mode = 1 # Dual Harmonic Mode
        self.lockin.harmonic1 = 1
        self.lockin.harmonic2 = 2
        self.lockin.phase1 = self.lockin_phase1
        self.lockin.phase2 = self.lockin_phase2
        self.lockin.sensitivity1 = self.sensitivity1
        self.lockin.sensitivity2 = self.sensitivity2
        self.lockin.time_constant1 = self.time_constant1
        self.lockin.time_constant2 = self.time_constant2

        log.info(f"Setting lockin voltage output to {self.applied_voltage} V")
        self.lockin.voltage = self.applied_voltage
        self.lockin.frequency = self.lockin_frequency
        self.lockin.reference = 'internal'

        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()

    def execute(self):
        # Make array of all field points to visit
        field_points = np.arange(self.field_strength_start,
                                    self.field_strength_end,
                                    self.field_strength_step)
        if self.field_strength_end not in field_points:
            field_points = np.append(field_points,self.field_strength_end)
        field_points = field_points[::-1] # reduce pole remnants
        
        if self.field_swap == 'None':
            pass
        elif self.field_swap == 'Hysteretic':
            field_points = np.concatenate((field_points,-1*field_points[::-1]))
            field_points = np.concatenate((-1*field_points, field_points))
        elif self.field_swap == 'Maximum':
            field_points = np.concatenate((field_points, -1*field_points))
        
        num_progress = field_points.size

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting magnetic field to {field} T")
            self.magnet.field = field
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "X2": self.lockin.x2,
                "Y1": self.lockin.y1,
                "Y2": self.lockin.y2,
                "field_strength": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class Hall2DualHarmFixedIPFieldProcedure(Hall2DualHarmBase):
    """
    Procedure for taking second harmonic Hall Measurements
    sweeping OOP field strength using Dual harmonic mode (one lockin) while
    applying a constant in-plane field
    """

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_IP_strength = FloatParameter("Fixed In Plane Field Strength", units="T", default=0.0)
    field_OOP_strength_start = FloatParameter("Initial OOP Field Strength", units="T", default=0.0)
    field_OOP_strength_end = FloatParameter("Final OOP Field Strength", units="T", default=0.1)
    field_OOP_strength_step = FloatParameter("OOP Field Strength Step", units="T", default=0.01)
    
    field_swap = Parameter("Field Swap")

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "OOP_field_strength", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, 1e-2):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} deg")
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

      # Lockin measuring harmonics
        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.set_voltage_mode()

        self.lockin.mode = 1 # Dual Harmonic Mode
        self.lockin.harmonic1 = 1
        self.lockin.harmonic2 = 2
        self.lockin.phase1 = self.lockin_phase1
        self.lockin.phase2 = self.lockin_phase2
        self.lockin.sensitivity1 = self.sensitivity1
        self.lockin.sensitivity2 = self.sensitivity2
        self.lockin.time_constant1 = self.time_constant1
        self.lockin.time_constant2 = self.time_constant2

        log.info(f"Setting lockin voltage output to {self.applied_voltage} V")
        self.lockin.voltage = self.applied_voltage
        self.lockin.frequency = self.lockin_frequency
        self.lockin.reference = 'internal'

        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()

    def execute(self):
        field_points = np.arange(self.field_OOP_strength_start,
                                 self.field_OOP_strength_end,
                                 self.field_OOP_strength_step)
        if self.field_OOP_strength_end not in field_points:
            field_points = np.append(field_points,self.field_OOP_strength_end)
        field_points = field_points[::-1] # reduce pole remnants

        if self.field_swap == 'None':
            pass
        elif self.field_swap == 'Hysteretic':
            field_points = np.concatenate((field_points,-1*field_points[::-1]))
            field_points = np.concatenate((-1*field_points, field_points[::-1]))
        elif self.field_swap == 'Maximum':
            field_points = np.concatenate((field_points, -1*field_points))
        
        num_progress = field_points.size

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field to %g T" % field)

            #Set theta from IP and OOP fields
            theta = np.arctan2(field, self.field_IP_strength)
            self.magnet.theta = theta*180./np.pi
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

            #Set field strength from vector sum of IP and OOP fields
            field_vector_sum = np.sqrt(self.field_IP_strength**2 + field**2)
            self.magnet.field = field_vector_sum

            sleep(self.delay)
            
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "X2": self.lockin.x2,
                "Y1": self.lockin.y1,
                "Y2": self.lockin.y2,
                "OOP_field_strength": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
