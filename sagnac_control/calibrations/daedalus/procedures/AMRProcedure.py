import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.agilent import Agilent8257D
from ..custom_instruments import daedalusProjField, Keithley220
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class AMRBase(Procedure):
    """
    Dummy procedure to define common parameters for AMR. Stay DRY folks.
    """
    
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    
    sample_name = Parameter("Sample Name", default='')
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    delay = FloatParameter("Delay", units="s", default=0.5)

    sensitivity = FloatParameter("Lockin Sensitivity", units="V", default=0.01)
    time_constant = FloatParameter("Lockin Time Constant", units="s", default=0.5)
    lockin_phase = FloatParameter("Lockin Phase Offset", units='deg', default=0)

    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)
    lockin_ac_gain = FloatParameter("Lockin AC Gain", units="dB", default=40.0)
    lockin_frequency = FloatParameter("Lockin Frequency", units="Hz", default=137.17)
    lockin_sense_mode = Parameter("Lockin Sense Mode")
    
    wheatsone_R1 = FloatParameter("Wheatstone R1 Fixed Resistance", units='Ohm', default=1886.)
    wheatsone_R2 = FloatParameter("Wheatstone R2 Variable Resistance", units='Ohm', default=100.)
    wheatsone_R3 = FloatParameter("Wheatstone R3 Fixed Resistance", units="Ohm", default=1936.)

    queued_time = Parameter('Time Queued')

    first = True
    last = True    

class AMRAngProcedure(AMRBase):
    """
    Procedure for taking AMR angle sweep measurements
    """

    field_azimuth_start = FloatParameter("Start Azimuthal Field", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Azimuthal Field", units="deg", default=0.1)
    field_azimuth_step = FloatParameter("Azimuthal Field Step", units="deg", default=0.05)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    DATA_COLUMNS = ["X","Y","field_azimuth_measured","field_azimuth","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)
        log.info("setting magnet polar orientation to %g degrees" % self.field_polar)
        self.magnet.theta = self.field_polar
        if self.first:
            voltage_pole_elim = np.sign(self.field_strength) * 10
            log.info("Setting magnet voltage to %g V to eliminate pole remnants"%voltage_pole_elim)
            self.magnet.volts = voltage_pole_elim
        log.info("setting magnet field strength to %g T" % self.field_strength)
        self.magnet.field = self.field_strength

        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.mode = 0 # Single Harmonic Mode
        self.lockin.set_voltage_mode()
        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()
        self.lockin.frequency = self.lockin_frequency
        self.lockin.gain = self.lockin_ac_gain
        self.lockin.sensitivity = self.sensitivity
        self.lockin.time_constant = self.time_constant
        self.lockin.phase = self.lockin_phase
        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin.voltage = self.applied_voltage

    def execute(self):
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end,self.field_azimuth_step)
        if self.field_azimuth_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_azimuth_end)

        num_progress = angles.size

        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting azimuthal field angle to %g deg" % angle)
            self.magnet.phi = angle
            # wait for all motion to finish
            while self.magnet.in_motion:
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            sleep(self.delay) # only for equilibration
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockin.x,
                "Y": self.lockin.y,
                "field_azimuth": angle,
                "field_azimuth_measured": self.magnet.phi,
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
            log.info("Done with one sweep, but more to go")
            sleep(1)

class AMRFieldBiasProcedure(AMRBase):
    """
    Procedure for taking AMR field sweep measurements with DC bias on the Daedalus setup
    """

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)

    field_strength_start = FloatParameter("Initial Field Strength", units="T", default=0.0)
    field_strength_end = FloatParameter("Final Field Strength", units="T", default=0.1)
    field_strength_step = FloatParameter("Field Strength Step", units="T", default=0.0005)
    
    field_swap = Parameter("Field Swap", default='None')

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("Bias Current", units="Amp", default=0.)

    DATA_COLUMNS = ["X","Y","field_strength","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info("setting magnet polar orientation to %g degrees" % self.field_polar)
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, 1e-2):
            log.info("setting magnet azimuthal orientation to %g degrees" % self.field_azimuth)
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        
        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.mode = 0 # Single Harmonic Mode
        self.lockin.set_voltage_mode()
        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()
        self.lockin.frequency = self.lockin_frequency
        self.lockin.gain = self.lockin_ac_gain
        self.lockin.sensitivity = self.sensitivity
        self.lockin.time_constant = self.time_constant
        self.lockin.phase = self.lockin_phase
        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin.voltage = self.applied_voltage

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info("Setting DC bias current to %g A"%self.dc_bias)
            self.bias_source.current = self.dc_bias

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
            field_points = np.concatenate((-1*field_points, field_points[::-1]))
        elif self.field_swap == 'Maximum':
            field_points = np.concatenate((field_points, -1*field_points))
        
        num_progress = field_points.size
        
        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info("Setting magnetic field to %g T" % field)
            self.magnet.field = field
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockin.x,
                "Y": self.lockin.y,
                "field_strength": self.magnet.field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Done with scans. Shutting down instruments")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)

class AMRDualHarmBase(Procedure):
    """
    Dummy procedure to define common parameters for AMR in the dual harmonic mode. 
    Stay DRY folks.
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    
    sample_name = Parameter("Sample Name", default='')
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    delay = FloatParameter("Delay", units="s", default=0.5)

    sensitivity1 = FloatParameter("First Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant1 = FloatParameter("First Harmonic Lockin Time Constant", units="s", default=0.5)
    lockin_phase1 = FloatParameter("First Harmonic Lockin Phase", units="deg", default=0.0)
    
    sensitivity2 = FloatParameter("Second Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant2 = FloatParameter("Second Harmonic Lockin Time Constant", units="s", default=0.5)
    lockin_phase2 = FloatParameter("Second Harmonic Lockin Phase", units="deg", default=0.0)

    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)
    lockin_ac_gain = FloatParameter("Lockin AC Gain", units="dB", default=40.0)
    lockin_frequency = FloatParameter("Lockin Frequency", units="Hz", default=137.71) 
    lockin_sense_mode = Parameter("Lockin Sense Mode")

    wheatsone_R1 = FloatParameter("Wheatstone R1 Fixed Resistance", units='Ohm', default=1886.)
    wheatsone_R2 = FloatParameter("Wheatstone R2 Variable Resistance", units='Ohm', default=100.)
    wheatsone_R3 = FloatParameter("Wheatstone R3 Fixed Resistance", units="Ohm", default=1936.)

    queued_time = Parameter('Time Queued')

    first = True
    last = True

class AMRAngDualHarmProcedure(AMRDualHarmBase):
    """
    Procedure for taking AMR angle sweep measurements using the dual harmonic
    feature of the lockin
    """

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
        log.info("setting magnet polar orientation to %g degrees" % self.field_polar)
        self.magnet.theta = self.field_polar
        if self.first:
            voltage_pole_elim = np.sign(self.field_strength) * 10
            log.info("Setting magnet voltage to %g V to eliminate pole remnants"%voltage_pole_elim)
            self.magnet.volts = voltage_pole_elim
        log.info("setting magnet field strength to %g T" % self.field_strength)
        self.magnet.field = self.field_strength


        # Lockin measuring harmonics
        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.set_voltage_mode()
        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()
        self.lockin.mode = 1 # Dual Harmonic Mode
        self.lockin.harmonic1 = 1
        self.lockin.harmonic2 = 2
        self.lockin.phase1 = self.lockin_phase1
        self.lockin.phase2 = self.lockin_phase2
        self.lockin.sensitivity1 = self.sensitivity1
        self.lockin.sensitivity2 = self.sensitivity2
        self.lockin.time_constant1 = self.time_constant1
        self.lockin.time_constant2 = self.time_constant2

        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin.reference = 'internal'
        self.lockin.voltage = self.applied_voltage
        self.lockin.frequency = self.lockin_frequency
        self.lockin.gain = self.lockin_ac_gain

    def execute(self):
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end,self.field_azimuth_step)
        if self.field_azimuth_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_azimuth_end)

        num_progress = angles.size

        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting azimuthal field angle to %g deg" % angle)
            self.magnet.phi = angle
            # wait for all motion to finish
            while self.magnet.in_motion:
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            sleep(self.delay) # only for equilibration
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "X2": self.lockin.x2,
                "Y1": self.lockin.y1,
                "Y2": self.lockin.y2,
                "field_azimuth": angle,
                "field_azimuth_measured": self.magnet.phi,
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
            log.info("Done with one sweep, but more to go")
            sleep(1)

class AMRFieldBiasDualHarmProcedure(AMRDualHarmBase):
    """
    Procedure for taking AMR field sweep measurements with the Daedalus setup
    """

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)

    field_strength_start = FloatParameter("Initial Field Strength", units="T", default=0.0)
    field_strength_end = FloatParameter("Final Field Strength", units="T", default=0.1)
    field_strength_step = FloatParameter("Field Strength Step", units="T", default=0.0005)
    
    field_swap = Parameter("Field Swap", default='None')

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("Bias Current", units="Amp", default=0.)

    DATA_COLUMNS = ["X1", "Y1", "X2", "Y2","field_strength","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info("setting magnet polar orientation to %g degrees" % self.field_polar)
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, 1e-2):
            log.info("setting magnet azimuthal orientation to %g degrees" % self.field_azimuth)
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

        # Lockin measuring harmonics
        self.lockin = DSP7265("GPIB::12") # "primary" lockin
        self.lockin.set_voltage_mode()
        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()
        self.lockin.mode = 1 # Dual Harmonic Mode
        self.lockin.harmonic1 = 1
        self.lockin.harmonic2 = 2
        self.lockin.phase1 = self.lockin_phase1
        self.lockin.phase2 = self.lockin_phase2
        self.lockin.sensitivity1 = self.sensitivity1
        self.lockin.sensitivity2 = self.sensitivity2
        self.lockin.time_constant1 = self.time_constant1
        self.lockin.time_constant2 = self.time_constant2

        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin.voltage = self.applied_voltage
        self.lockin.frequency = self.lockin_frequency
        self.lockin.reference = 'internal'
        self.lockin.gain = self.lockin_ac_gain
        
        if self.use_bias: 
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info("Setting DC bias current to %g A"%self.dc_bias)
            self.bias_source.current = self.dc_bias

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
            field_points = np.concatenate((-1*field_points, field_points[::-1]))
        elif self.field_swap == 'Maximum':
            field_points = np.concatenate((field_points, -1*field_points))
        
        num_progress = field_points.size

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info("Setting magnetic field to %g T" % field)
            self.magnet.field = field
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "Y1": self.lockin.y1,
                "X2": self.lockin.x2,
                "Y2": self.lockin.y2,
                "field_strength": self.magnet.field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Done with scans. Shutting down instruments")
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)
