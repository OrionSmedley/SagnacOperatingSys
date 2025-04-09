import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.agilent import Agilent8257D
from ..custom_instruments import daedalusProjField, Keithley220
from pymeasure.instruments.keithley import Keithley2182A
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class HallOOPProcedure(Procedure):
    """
    Procedure for taking out-of-plane Hall Measurements with the Daedalus setup
    """
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')

    sample_name = Parameter("Sample Name", default='')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)

    field_strength_z_start = FloatParameter("Start z Magnetic Field", units="T", default=0.)
    field_strength_z_end = FloatParameter("End z Magnetic Field", units="T", default=0.1)
    field_strength_z_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)

    field_strength_ip = FloatParameter("In plane Magnetic Field", units="T", default=0.)

    delay = FloatParameter("Delay", units="s", default=0.5)

    sensitivity = FloatParameter("Lockin Sensitivity", units="V", default=0.01)
    time_constant = FloatParameter("Lockin Time Constant", units="s", default=0.5)
    lockin_voltage = FloatParameter("Lockin Voltage", units="V", default=0.0)

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("DC Bias Current", units='A', default=1e-4)

    queued_time = Parameter('Time Queued')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ["X","Y","field_strength_z","elapsed_time","field_polar"]

    def startup(self):
        # TODO: Look for more setup stuff to be done.
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)

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

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info("Setting DC bias current to %g A"%self.dc_bias)
            self.bias_source.current = self.dc_bias

    def execute(self):
        field_points = np.arange(self.field_strength_z_start,
                                 self.field_strength_z_end,
                                 self.field_strength_z_step)
        if self.field_strength_z_end not in field_points:
            field_points = np.append(field_points,self.field_strength_z_end)
        field_points = np.concatenate([field_points, field_points[::-1]])
        num_progress = field_points.size
        start_time = time()

        for progress_iterator, fieldz in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field in the z direction to %g T" % fieldz)
            B = np.sqrt(fieldz**2 + self.field_strength_ip**2)
            theta_ = np.arctan2(fieldz, self.field_strength_ip)*180/np.pi # convert to our convention
            self.magnet.set_vector_field(B, phi=self.field_azimuth, theta=theta_)
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockin.x,
                "Y": self.lockin.y,
                "field_strength_z": fieldz,
                "field_polar": theta_,
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
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class HallOOPVoltmeterProcedure(Procedure):
    """
    Procedure for taking out-of-plane Hall Measurements with the Daedalus setup
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')

    sample_name = Parameter("Sample Name", default='')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)

    field_strength_z_start = FloatParameter("Start z Magnetic Field", units="T", default=0.)
    field_strength_z_end = FloatParameter("End z Magnetic Field", units="T", default=0.1)
    field_strength_z_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)

    field_strength_ip = FloatParameter("In plane Magnetic Field", units="T", default=0.)

    delay = FloatParameter("Delay", units="s", default=0.5)

    voltage_range = FloatParameter("Nanovoltmeter Range", units="V", default=0.01)

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("DC Bias Current", units='A', default=1e-4)

    queued_time = Parameter('Time Queued')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ["hall_voltage","field_strength_z","elapsed_time","field_polar"]

    def startup(self):
        # TODO: Look for more setup stuff to be done.
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::1")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)

        self.voltmeter = Keithley2182A("GPIB::8") # TODO: figure out GPIB address
        if not self.voltmeter.calibration_is_good():
            log.warning("Nanovoltmeter calibration is not good! It should be redone")
        self.voltmeter.set_voltage_mode()
        self.voltmeter.channel = 1
        self.voltmeter.enable_low_pass_filter()
        self.voltmeter.rate = 2 # TODO: Figure out good value for this
        self.voltmeter.voltage_range = self.voltage_range
        # TODO: Digital filter setup?

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info("Setting DC bias current to %g A"%self.dc_bias)
            self.bias_source.current = self.dc_bias

    def execute(self):
        field_points = np.arange(self.field_strength_z_start,
                                 self.field_strength_z_end,
                                 self.field_strength_z_step)
        if self.field_strength_z_end not in field_points:
            field_points = np.append(field_points,self.field_strength_z_end)
        field_points = np.concatenate([field_points, field_points[::-1]])
        num_progress = field_points.size
        start_time = time()

        for progress_iterator, fieldz in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field in the z direction to %g T" % fieldz)
            B = np.sqrt(fieldz**2 + self.field_strength_ip**2)
            theta_ = np.arctan2(fieldz, self.field_strength_ip)*180/np.pi # convert to our convention
            self.magnet.set_vector_field(B, phi=self.field_azimuth, theta=theta_)

            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "hall_voltage": self.voltmeter.voltage,
                "field_strength_z": fieldz,
                "field_polar": theta_,
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
            # self.lockin.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
