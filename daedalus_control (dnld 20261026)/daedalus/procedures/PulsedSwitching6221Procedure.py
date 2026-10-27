import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.agilent import Agilent8257D
from pymeasure.instruments.keithley import Keithley2400
from daedalus.custom_instruments import daedalusProjField, DAQmxAdapter, DSP7265, daedalusProjFieldYokogawa, Keithley6221
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from time import sleep, time
import numpy as np

class PulsedSwitching6221Procedure(Procedure):
    """
    Procedure for doing pulsed switching measurements on daedlus
    """
    calib_file = Parameter("Magnet Calibration Filename", default='')
    station_name = Parameter("Probe Station Name", default='')
    
    sample_name = Parameter("Sample Name", default='')

    # Parameters for lockin
    ac_current = FloatParameter("AC Current", units="A", default=2e-6)
    lockin_freq = FloatParameter("Lockin Frequency", units = 'Hz', default=1317.17)
    sensitivity = FloatParameter("Lockin Sensitivity", units="V", default=2e-6)
    time_constant = FloatParameter("Lockin Time Constant", units="s", default=0.5)
    
    # Parameters for Bx field
    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_strength_ip = FloatParameter("In plane Magnetic Field", units="T", default=0.)
    
    # Parameters for current
    current_pulse_start = FloatParameter("Current Pulse Start", units = "A", default =0.)
    current_pulse_end = FloatParameter("Current Pulse End", units = "A", default = 0.)
    current_pulse_step = FloatParameter("Current Pulse Step", units = "A", default = 0.)
    width = FloatParameter("Current Pulse Width", units = 's', default = 5e-6)

    delay = FloatParameter("Delay", units="s", default=0.5)
    queued_time = Parameter('Time Queued')
    
    first = True
    last = True
    DATA_COLUMNS = ["X1","Y1", "X2", "Y2", "current","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        self.magnet = daedalusProjFieldYokogawa("GPIB::2","GPIB::10")
        for err in self.magnet.errors:
            log.warning(f'{err}')
        
        self.magnet.load_calibration_params(self.calib_file)
        log.info("Connected to Magnet")

        self.current_source = Keithley6221("GPIB::06")
        log.info("Connected to Keithley 6221 ac+dc current source")

        self.lockin = DSP7265("GPIB::12")
        self.lockin.time_constant = self.time_constant
        self.lockin.sensitivity = self.sensitivity
        log.info("Connected to Lockin")

    def execute(self):
        current_points = np.arange(self.current_pulse_start, 
                                    self.current_pulse_end, 
                                    self.current_pulse_step)# All the current points
        
        if self.current_pulse_end not in current_points:
            current_points = np.append(current_points,self.current_pulse_end)
        current_points = np.concatenate([current_points, current_points[::-1]])
        num_progress = current_points.size

        self.magnet.set_vector_field(self.field_strength_ip, phi=self.field_azimuth, theta=0)
        log.info("Setting magnetic field to %g T" % self.field_strength_ip)
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.5)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        start_time  = time()

        for progress_iterator, current in enumerate(current_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Pulse Current %g A", current)
            self.current_source.stop_wave()
            self.current_source.output = 0
            self.current_source.clear()
            self.current_source.auto_range = 1
            self.current_source.output = 1
            self.current_source.ramp_to_current(current, steps = 4, pause = 1e-6)
            sleep(self.width)
            log.info("Width %g s", self.width)
            self.current_source.ramp_to_current(0, steps = 4, pause = 1e-6)
            self.current_source.output = 0

            sleep(2)
            log.info("Starting AC")
            self.current_source.clear()
            self.current_source.wave_freq = self.lockin_freq
            log.info("Keithley 6221 set to %g Hz", self.lockin_freq)
            self.current_source.wave_amp = self.ac_current
            log.info("Keithley 6221 ac amplitude set to %g A", self.ac_current)
            self.current_source.wave_offset = 0.0
            self.current_source.enable_phase_marker()
            self.current_source.set_best_range()
            self.current_source.arm_wave()
            self.current_source.start_wave()
            sleep(3)

            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "Y1": self.lockin.y1,
                "X2": self.lockin.x2,
                "Y2": self.lockin.y2,
                "current": current,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.lockin.shutdown()
            self.current_source.shutdown()
            self.magnet.set_vector_field(0,0,0)
            self.magnet.shutdown()
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class SweepSwitching6221Procedure(Procedure):
    """
    Procedure for doing pulsed switching measurements on daedlus
    """
    calib_file = Parameter("Magnet Calibration Filename", default='')
    station_name = Parameter("Probe Station Name", default='')
    
    sample_name = Parameter("Sample Name", default='')

    # Parameters for lockin
    ac_current = FloatParameter("AC Current", units="A", default=2e-6)
    lockin_freq = FloatParameter("Lockin Frequency", units = 'Hz', default=1317.17)
    sensitivity = FloatParameter("Lockin Sensitivity", units="V", default=2e-6)
    time_constant = FloatParameter("Lockin Time Constant", units="s", default=0.5)
    
    # Parameters for Bx field
    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_strength_ip = FloatParameter("In plane Magnetic Field", units="T", default=0.)
    
    # Parameters for current
    current_pulse_start = FloatParameter("Current Pulse Start", units = "A", default =0.)
    current_pulse_end = FloatParameter("Current Pulse End", units = "A", default = 0.)
    current_pulse_step = FloatParameter("Current Pulse Step", units = "A", default = 0.)
    width = FloatParameter("Current Pulse Width", units = 's', default = 5e-6)

    delay = FloatParameter("Delay", units="s", default=0.5)
    queued_time = Parameter('Time Queued')
    
    first = True
    last = True
    DATA_COLUMNS = ["X1","Y1", "X2", "Y2", "current","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        self.magnet = daedalusProjFieldYokogawa("GPIB::2","GPIB::10")
        for err in self.magnet.errors:
            log.warning(f'{err}')
        
        self.magnet.load_calibration_params(self.calib_file)
        log.info("Connected to Magnet")

        self.current_source = Keithley6221("GPIB::06")
        log.info("Connected to Keithley 6221 ac+dc current source")

        self.lockin = DSP7265("GPIB::12")
        self.lockin.time_constant = self.time_constant
        self.lockin.sensitivity = self.sensitivity
        log.info("Connected to Lockin")

    def execute(self):
        current_points = np.arange(self.current_pulse_start, 
                                    self.current_pulse_end, 
                                    self.current_pulse_step)# All the current points
        
        if self.current_pulse_end not in current_points:
            current_points = np.append(current_points,self.current_pulse_end)
        current_points = np.concatenate([current_points, current_points[::-1]])
        num_progress = current_points.size

        self.magnet.set_vector_field(self.field_strength_ip, phi=self.field_azimuth, theta=0)
        log.info("Setting magnetic field to %g T" % self.field_strength_ip)
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.5)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        start_time  = time()

        self.current_source.clear()
        self.current_source.wave_freq = self.lockin_freq
        log.info("Keithley 6221 set to %g Hz", self.lockin_freq)
        self.current_source.wave_amp = self.ac_current
        log.info("Keithley 6221 ac amplitude set to %g A", self.ac_current)

        for progress_iterator, current in enumerate(current_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            self.current_source.stop_wave()
            self.current_source.wave_offset = current
            self.current_source.enable_phase_marker()
            self.current_source.set_best_range()
            self.current_source.arm_wave()
            self.current_source.start_wave()
            sleep(3)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin.x1,
                "Y1": self.lockin.y1,
                "X2": self.lockin.x2,
                "Y2": self.lockin.y2,
                "current": current,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.lockin.shutdown()
            self.current_source.shutdown()
            self.magnet.set_vector_field(0,0,0)
            self.magnet.shutdown()
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

