import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.keithley import Keithley2400
from daedalus.custom_instruments import daedalusProjFieldYokogawa, DAQmxAdapter, DSP7265, Keithley6221, daedalusProjFieldDAQ, Keithley220, Keithley2182A
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from time import sleep, time
import numpy as np

class HallNanovoltmeterBase(Procedure):
    """
    Dummy procedure to define common parameters for 2nd harmonic Hall.
    """
    
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')
    
    delay = FloatParameter("Delay", units="s", default=0.5)

    applied_current = FloatParameter("Applied Current", units='A', default=1e-3)
    nvolt_range = FloatParameter("Nanovoltmeter Range", units="V", default=1)
    nvolt_rate = FloatParameter("Nanovoltmeter Measurement Rate", units="NPLC", default=1.0)
    nvolt_analog_filter = BooleanParameter("Nanovoltmeter Use Analog Filter?", default=False)
    nvolt_digital_filter = BooleanParameter("Nanovoltmeter Use Digital Filter?", default=False)
    nvolt_n_dfilt = IntegerParameter("Nanovoltmeter Digital Filter Averages", default=5)
    nvolt_dfilt_type = Parameter("Nanovoltmeter Digital Filter Type", default='repeating')
    nvolt_diflt_window = FloatParameter("Nanovoltmeter Digital Filter Window", default=0)
    
    volt_compliance = FloatParameter("Voltage Compliance", units ='V', default=1e-2)

    queued_time = Parameter('Time Queued')

    first = True
    last = True 
    
class HallNanovoltmeterAngProcedure(HallNanovoltmeterBase):
    """
    Procedure for taking second harmonic Hall Measurements sweeping azimuthal
    (in-plane) angle
    """

    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_azimuth_start = FloatParameter("Start Azimuthal Field", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Azimuthal Field", units="deg", default=0.1)
    field_azimuth_step = FloatParameter("Azimuthal Field Step", units="deg", default=0.05)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    DATA_COLUMNS = ["field_azimuth", "Vxx", "Vxy", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        self.magnet = daedalusProjFieldDAQ(DAQmxAdapter("Dev1", ['ao0', 'ai4']),"GPIB::10")
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

        self.voltmeter = Keithley2182A("GPIB::8")
        #if not self.voltmeter.calibration_is_good():
            #log.warning("Nanovoltmeter calibration is not good! It should be redone")
        #self.voltmeter.set_voltage_mode()
        #self.voltmeter.channel = 1
        #if self.nvolt_analog_filter:
         #self.voltmeter.enable_low_pass_filter()
        #else:
           # self.voltmeter.disable_low_pass_filter()
        #if self.nvolt_digital_filter:
           # self.voltmeter.configure_digital_filter(self.nvolt_diflt_window, self.nvolt_n_dfilt, self.nvolt_dfilt_type)
        #else:
           # self.voltmeter.disable_digital_filter()
        #self.voltmeter.rate = self.nvolt_rate
        #self.voltmeter.voltage_range = self.nvolt_range

        self.sourcemeter = Keithley2400("GPIB::4")
        #self.sourcemeter.apply_current(current_range=self.applied_current*1.05, compliance_voltage=self.volt_compliance)
        #self.sourcemeter.measure_voltage(voltage=2.1, auto_range=False)
        #self.sourcemeter.source_current = self.applied_current
        #self.sourcemeter.enable_source()

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
                "field_azimuth": self.magnet.phi,
                "Vxy": self.voltmeter.voltage,
                "Vxx": self.sourcemeter.voltage[0],
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scan. Shutting down instruments.")
            self.magnet.volts = 0
            # self.sourcemeter.disable_source()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)