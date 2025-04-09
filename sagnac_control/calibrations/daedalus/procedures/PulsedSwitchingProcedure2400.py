import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.agilent import Agilent8257D, Agilent33250A	
from ..custom_instruments import daedalusProjField, Keithley220
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from pymeasure.instruments.keithley import Keithley2400
from time import sleep, time
import numpy as np

class Pulsed_Switching2400(Procedure):
    """
    Procedure for doing pulsed switching measurements on daedlus
    """
    calib_file = Parameter("Magnet Calibration Filename", default='')
    station_name = Parameter("Probe Station Name", default='')
    
    sample_name = Parameter("Sample Name", default='')
    delay = FloatParameter("Delay", units="s", default=0.5)
    sensitivity = FloatParameter("Lockin Sensitivity", units="V", default=0.01)
    time_constant = FloatParameter("Lockin Time Constant", units="s", default=0.5)
    lockin_voltage = FloatParameter("Lockin current", units="V", default=0.0)
    frequency = FloatParameter("Function Generator frequency", units = 'Hz', default=100)
    width = FloatParameter("Function Generator Pulse Width", units = 's', default = 1e-3)
    queued_time = Parameter('Time Queued')

    # Parameters for Bx field
    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_strength_ip = FloatParameter("In plane Magnetic Field", units="T", default=0.)
    # Parameters for current
    current_function_gen_start = FloatParameter("Current Function Generator Start", units = "A", default =0.)
    current_function_gen_end = FloatParameter("Current Function Generator End", units = "A", default = 0.)
    current_function_gen_step = FloatParameter("Current Function Generator Step", units = "A", default = 0.)
    DATA_COLUMNS = ["X","Y","current","elapsed_time"]
    first = True
    last = True
    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)

        # Initialising the lockin amplufier
        self.lockin = DSP7265("GPIB::12")
        self.lockin.set_voltage_mode()
        self.lockin.setChannelAMode()
        self.lockin.time_constant = self.time_constant
        self.lockin.sensitivity = self.sensitivity
        self.lockin.harmonic = 1
        self.lockin.phase = 0.
        self.lockin.voltage_input_device = 'FET'
        self.lockin.input_coupling = 'AC'
        self.lockin.reference = 'internal'
        self.lockin.frequency = 1713.0
        self.lockin.voltage = self.lockin_voltage
        # Initialising the function generator
        self.current_source = Keithley2400("GPIB::14")# Figure out the GPIB address
    def execute(self):
        current_points = np.arange(self.current_function_gen_start, self.current_function_gen_end, self.current_function_gen_step)# All the current points
        if self.current_function_gen_end not in current_points:
            current_points = np.append(current_points,self.current_function_gen_end)
        current_points = np.concatenate([current_points, current_points[::-1]])
        num_progress = current_points.size
        self.magnet.set_vector_field(self.field_strength_ip, phi=self.field_azimuth, theta=0)
        log.info("Setting magnetic field to %g T" % self.field_strength_ip)
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        start_time  = time()
        
        self.current_source.ramp_to_current(self.current_function_gen_start, steps=50, pause = 20e-3)
        sleep(2.0)
        self.current_source.enable_source()

        for progress_iterator, current in enumerate(current_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            self.current_source.ramp_to_current(current, steps = 2, pause = 1e-3)
            sleep(5e-3)
            sleep(self.width)
            self.current_source.ramp_to_current(0, steps = 2, pause = 1e-3)
            sleep(5e-3)
            sleep(1/self.frequency - self.width)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockin.x,
                "Y": self.lockin.y,
                "current": current,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.magnet.set_vector_field(0,0,0)
            self.magnet.shutdown()
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin.shutdown()
            self.current_source.disable_source()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
