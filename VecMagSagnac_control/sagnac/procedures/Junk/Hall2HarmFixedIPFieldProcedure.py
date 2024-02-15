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

class Hall2HarmFixedIPFieldProcedure(Procedure):
    """
    Procedure for taking second harmonic Hall Measurements with the Daedalus setup,
    with field swept instead of angle.
    """

    sample_name = Parameter("Sample Name", default='')

    mag_calib_name = Parameter("Magnet Calibration Filename", default='./calibrations/proj_field')
    delay = FloatParameter("Delay", units="s", default=0.5)

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_IP_strength = FloatParameter("Fixed In Plane Field Strength", units="T", default=0.0)
    field_OOP_strength_start = FloatParameter("Initial OOP Field Strength", units="T", default=0.0)
    field_OOP_strength_end = FloatParameter("Final OOP Field Strength", units="T", default=0.1)
    field_OOP_strength_step = FloatParameter("OOP Field Strength Step", units="T", default=0.01)
    field_OOP_swap = BooleanParameter("Swap Field", default=True)

    sensitivity1 = FloatParameter("First Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant1 = FloatParameter("First Harmonic Lockin Time Constant", units="s", default=0.5)
    sensitivity2 = FloatParameter("Second Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant2 = FloatParameter("Second Harmonic Lockin Time Constant", units="s", default=0.5)

    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)

    queued_time = Parameter('Time Queued')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_strength", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.mag_calib_name)

        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, 1e-2):
            log.info("setting magnet azimuthal orientation to %g degrees" % self.field_azimuth)
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

        # Lockin measuring first harmonic
        self.lockin1 = DSP7265("GPIB::27") # "secondary" lockin
        self.lockin1.set_voltage_mode()
        self.lockin1.setDifferentialMode()
        self.lockin1.time_constant = self.time_constant1
        self.lockin1.sensitivity = self.sensitivity1
        self.lockin1.harmonic = 1
        self.lockin1.reference = 'external rear'

        # Lockin measuring second harmonic and driving current
        self.lockin2 = DSP7265("GPIB::28") # "primary" lockin
        self.lockin2.set_voltage_mode()
        self.lockin2.setDifferentialMode()
        self.lockin2.time_constant = self.time_constant2
        self.lockin2.sensitivity = self.sensitivity2
        self.lockin2.harmonic = 2
        self.lockin2.reference = 'internal'
        self.lockin2.frequency = 1713.0
        self.lockin2.phase = 90. # second harmonic is cos(2wt)
        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin2.voltage = self.applied_voltage

    def execute(self):
        field_points = np.arange(self.field_OOP_strength_start,
                                 self.field_OOP_strength_end,
                                 self.field_OOP_strength_step)
        if self.field_OOP_strength_end not in field_points:
            field_points = np.append(field_points,self.field_OOP_strength_end)
        field_points = field_points[::-1] # reduce pole remnants

        if self.field_swap:
            num_progress = field_points.size*2
        else:
            num_progress = field_points.size

        # Eliminate pole remnants/make measurements reproducible
        voltage_pole_elim = np.sign(field_points[0]) * 10
        log.info("Setting magnet voltage to %g V to eliminate pole remnants"%voltage_pole_elim)
        self.magnet.volts = voltage_pole_elim

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field to %g T" % field)

            #Set theta from IP and OOP fields
            theta = np.arctan2(field, self.field_IP_strength)
            self.magnet.theta = theta
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

            #Set field strength from vector sum of IP and OOP fields
            field_vector_sum = np.sqrt(self.field_IP_strength**2 + field)
            self.magnet.field = field_vector_sum

            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x,
                "X2": self.lockin2.x,
                "Y1": self.lockin1.y,
                "Y2": self.lockin2.y,
                "OOP_field_strength": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break
        if self.field_swap:
            if not self.should_stop():
                # Eliminate pole remnants/make measurements reproducible
                voltage_pole_elim = -1 * np.sign(field_points[0]) * 10
                log.info("Setting magnet voltage to %g V to eliminate pole remnants"%voltage_pole_elim)
                self.magnet.volts = voltage_pole_elim
                for progress_iterator, field in enumerate(-1*field_points):
                    self.emit("progress", int(100*(0.5+progress_iterator/num_progress)))
                    log.info("Setting magnetic field to %.2f T" % field)
                    
                    #Set theta from IP and OOP fields
                    theta = np.arctan2(field, self.field_IP_strength)
                    self.magnet.theta = theta
                    while self.magnet.in_motion: # wait for all motion to finish
                        sleep(0.1)
                    for err in self.magnet.errors:
                        log.warning('%s'%err)

                    #Set field strength from vector sum of IP and OOP fields
                    field_vector_sum = np.sqrt(self.field_IP_strength**2 + field)
                    self.magnet.field = field_vector_sum
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
