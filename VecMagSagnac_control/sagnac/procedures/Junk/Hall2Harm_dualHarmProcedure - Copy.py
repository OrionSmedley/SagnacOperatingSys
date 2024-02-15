import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.agilent import Agilent8257D
from ..custom_instruments import daedalusProjField, senis3AxHallProbe
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class Hall2HarmAng_dualHarmProcedure(Procedure):
    """
    Procedure for taking second harmonic Hall Measurements with the Daedalus setup
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')

    sample_name = Parameter("Sample Name", default='undefined')

    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_azimuth_start = FloatParameter("Start Azimuthal Field", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Azimuthal Field", units="deg", default=0.1)
    field_azimuth_step = FloatParameter("Azimuthal Field Step", units="deg", default=0.05)

    delay = FloatParameter("Delay", units="s", default=0.5)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    phase1 = FloatParameter("First Harmonic Lockin Phase", units="deg", default=0.0)
    phase2 = FloatParameter("Second Harmonic Lockin Phase", units="deg", default=0.0)
    sensitivity1 = FloatParameter("First Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant1 = FloatParameter("First Harmonic Lockin Time Constant", units="s", default=0.5)
    sensitivity2 = FloatParameter("Second Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant2 = FloatParameter("Second Harmonic Lockin Time Constant", units="s", default=0.5)
    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)
    frequency = FloatParameter("Lockin frequency", units='Hz', default=136.17)
    lockin_channel = IntegerParameter("Lockin channel", default=0)
    queued_time = Parameter('Time Queued')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

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
        self.lockin1 = DSP7265("GPIB::12") # "primary" lockin
        self.lockin1.set_voltage_mode()
        self.lockin1.mode = 1 # Dual Harmonic Mode
        self.lockin1.harmonic1 = 1
        self.lockin1.harmonic2 = 2
        self.lockin1.phase1 = self.phase1
        self.lockin1.phase2 = self.phase2
        self.lockin1.sensitivity1 = self.sensitivity1
        self.lockin1.sensitivity2 = self.sensitivity2
        self.lockin1.time_constant1 = self.time_constant1
        self.lockin1.time_constant2 = self.time_constant2

        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin1.voltage = self.applied_voltage
        self.lockin1.frequency = self.frequency
        self.lockin1.reference = 'internal'

        if self.lockin_channel == 0:
            log.info("Set Lockin channel to A")
            self.lockin1.setChannelAMode()

        if self.lockin_channel == 1:
            log.info("Set Lockin channel to A-B")
            self.lockin1.setDifferentialMode()

    def execute(self):
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end, self.field_azimuth_step)
        if self.field_azimuth_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_azimuth_end)

        num_progress = angles.size
        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting azimuthal field angle to %g deg" % angle)
            self.magnet.phi = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x1,
                "X2": self.lockin1.x2,
                "Y1": self.lockin1.y1,
                "Y2": self.lockin1.y2,
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
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)

class Hall2HarmPolarAng_dualHarmProcedure(Procedure):
    """
    Procedure for taking second harmonic Hall Measurements with the Daedalus setup
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')

    sample_name = Parameter("Sample Name", default='undefined')

    field_azimuth = FloatParameter("Magnetic Field Azimuth Angle", units="deg", default=0.)

    field_polar_start = FloatParameter("Start Polar Field", units="deg", default=0.)
    field_polar_end = FloatParameter("End Polar Field", units="deg", default=0.1)
    field_polar_step = FloatParameter("Polar Field Step", units="deg", default=0.05)

    delay = FloatParameter("Delay", units="s", default=0.5)

    field_strength = FloatParameter("Field Strength", units="T", default=0.0)

    phase1 = FloatParameter("First Harmonic Lockin Phase", units="deg", default=0.0)
    phase2 = FloatParameter("Second Harmonic Lockin Phase", units="deg", default=0.0)
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

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "field_polar_measured", "field_polar", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        self.magnet.load_calibration_params(self.calib_file)
        
        log.info("setting magnet azimuthal orientation to %g degrees" % self.field_azimuth)
        self.magnet.phi = self.field_azimuth
        if self.first:
            voltage_pole_elim = np.sign(self.field_strength) * 10
            log.info("Setting magnet voltage to %g V to eliminate pole remnants"%voltage_pole_elim)
            self.magnet.volts = voltage_pole_elim
        log.info("setting magnet field strength to %g T" % self.field_strength)
        self.magnet.field = self.field_strength

       # Lockin measuring harmonics
        self.lockin1 = DSP7265("GPIB::12") # "primary" lockin
        self.lockin1.set_voltage_mode()
        self.lockin1.setDifferentialMode()
        self.lockin1.phase1 = self.phase1
        self.lockin1.phase2 = self.phase2
        self.lockin1.sensitivity1 = self.sensitivity1
        self.lockin1.sensitivity2 = self.sensitivity2
        self.lockin1.time_constant1 = self.time_constant1
        self.lockin1.time_constant2 = self.time_constant2
        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin1.voltage = self.applied_voltage


    def execute(self):
        angles = np.arange(self.field_polar_start,
                           self.field_polar_end, self.field_polar_step)
        if self.field_polar_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_polar_end)

        num_progress = angles.size
        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting polar field angle to %g deg" % angle)
            self.magnet.theta = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x1,
                "X2": self.lockin1.x2,
                "Y1": self.lockin1.y1,
                "Y2": self.lockin1.y1,
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
            self.lockin1.shutdown()
        else:
            log.info("Done with one scan, but more to go.")
            sleep(1)

class Hall2HarmField_dualHarmProcedure(Procedure):
    """
    Procedure for taking second harmonic Hall Measurements with the Daedalus setup,
    with field swept instead of angle.
    """
    
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')

    sample_name = Parameter("Sample Name", default='')

    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)
    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)

    delay = FloatParameter("Delay", units="s", default=0.5)

    field_strength_start = FloatParameter("Field Strength", units="T", default=0.0)
    field_strength_end = FloatParameter("Final Field Strength", units="T", default=0.1)
    field_strength_step = FloatParameter("Field Strength Step", units="T", default=0.01)
    field_swap = BooleanParameter("Swap Field", default=True)

    phase1 = FloatParameter("First Harmonic Lockin Phase", units="deg", default=0.0)
    phase2 = FloatParameter("Second Harmonic Lockin Phase", units="deg", default=0.0)
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
        self.lockin1 = DSP7265("GPIB::12") # "primary" lockin
        self.lockin1.set_voltage_mode()
        self.lockin1.setDifferentialMode()
        self.lockin1.phase1 = self.phase1
        self.lockin1.phase2 = self.phase2
        self.lockin1.sensitivity1 = self.sensitivity1
        self.lockin1.sensitivity2 = self.sensitivity2
        self.lockin1.time_constant1 = self.time_constant1
        self.lockin1.time_constant2 = self.time_constant2
        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin1.voltage = self.applied_voltage


    def execute(self):
        field_points = np.arange(self.field_strength_start,
                                 self.field_strength_end,
                                 self.field_strength_step)
        if self.field_strength_end not in field_points:
            field_points = np.append(field_points,self.field_strength_end)
        field_points = field_points[::-1] # reduce pole remnants

        if self.field_swap:
            num_progress = field_points.size*2
        else:
            num_progress = field_points.size

        # Eliminate pole remnants/make measurements reproducible
        voltage_pole_elim = -np.sign(field_points[0]) * 10
        log.info("Setting magnet voltage to %g V to eliminate pole remnants"%voltage_pole_elim)
        self.magnet.volts = voltage_pole_elim

        start_time = time()


        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field to %g T" % field)
            self.magnet.field = field
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x1,
                "X2": self.lockin1.x2,
                "Y1": self.lockin1.y1,
                "Y2": self.lockin1.y2,
                "field_strength": field,
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
                    self.magnet.field = field
                    sleep(self.delay)
                    log.info("Recording results")
                    self.emit('results', {
                        "X1": self.lockin1.x1,
                        "X2": self.lockin1.x2,
                        "Y1": self.lockin1.y1,
                        "Y2": self.lockin1.y2,
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
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class Hall2HarmFixedIPField_dualHarmProcedure(Procedure):
    """
    Procedure for taking second harmonic Hall Measurements with the Daedalus setup,
    with field swept instead of angle.
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')

    sample_name = Parameter("Sample Name", default='')
    delay = FloatParameter("Delay", units="s", default=0.5)

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_IP_strength = FloatParameter("Fixed In Plane Field Strength", units="T", default=0.0)
    field_OOP_strength_start = FloatParameter("Initial OOP Field Strength", units="T", default=0.0)
    field_OOP_strength_end = FloatParameter("Final OOP Field Strength", units="T", default=0.1)
    field_OOP_strength_step = FloatParameter("OOP Field Strength Step", units="T", default=0.01)
    field_OOP_swap = BooleanParameter("Swap Field", default=True)
    
    phase1 = FloatParameter("First Harmonic Lockin Phase", units="deg", default=0.0)
    phase2 = FloatParameter("Second Harmonic Lockin Phase", units="deg", default=0.0)
    sensitivity1 = FloatParameter("First Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant1 = FloatParameter("First Harmonic Lockin Time Constant", units="s", default=0.5)
    sensitivity2 = FloatParameter("Second Harmonic Lockin Sensitivity", units="V", default=0.01)
    time_constant2 = FloatParameter("Second Harmonic Lockin Time Constant", units="s", default=0.5)
    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)
    applied_voltage = FloatParameter("Applied Sample Voltage", units='V',default=0.)

    queued_time = Parameter('Time Queued')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ["X1", "X2", "Y1", "Y2", "OOP_field_strength", "Xfield_avg","Yfield_avg","Zfield_avg","Xfield_std", "Yfield_std", "Zfield_std", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev2', ['ai0','ai2','ai4']))
        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)
        self.x_zero, self.y_zero, self.z_zero = np.loadtxt(self.calib_file + '_hall_probe_zero_calib.csv', delimiter=',')
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, 1e-2):
            log.info("setting magnet azimuthal orientation to %g degrees" % self.field_azimuth)
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

              # Lockin measuring harmonics
        self.lockin1 = DSP7265("GPIB::12") # "primary" lockin
        self.lockin1.set_voltage_mode()
        self.lockin1.setDifferentialMode()
        self.lockin1.phase1 = self.phase1
        self.lockin1.phase2 = self.phase2
        self.lockin1.sensitivity1 = self.sensitivity1
        self.lockin1.sensitivity2 = self.sensitivity2
        self.lockin1.time_constant1 = self.time_constant1
        self.lockin1.time_constant2 = self.time_constant2
        log.info("Setting lockin voltage output to %g V"%self.applied_voltage)
        self.lockin1.voltage = self.applied_voltage

    def get_Bx_zeroed(self):
        return (self.hall_probe.x_field - self.x_zero)

    def get_By_zeroed(self):
        return (self.hall_probe.y_field - self.y_zero)

    def get_Bz_zeroed(self):
        return -1*(self.hall_probe.z_field - self.z_zero)

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
            self.magnet.theta = theta*180./np.pi
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

            #Set field strength from vector sum of IP and OOP fields
            field_vector_sum = np.sqrt(self.field_IP_strength**2 + field**2)
            self.magnet.field = field_vector_sum

            sleep(self.delay)

            xfields = np.array([])
            yfields = np.array([])
            zfields = np.array([])
            
            for i in range(5):
                sleep(self.delay)
                xfields = np.append(xfields,self.get_Bx_zeroed())
                yfields = np.append(yfields,self.get_By_zeroed())
                zfields = np.append(zfields,self.get_Bz_zeroed())

            Bmag = np.sqrt(np.mean(xfields)**2 + np.mean(yfields)**2 + np.mean(zfields)**2)
            
            log.info("Recording results")
            self.emit('results', {
                "X1": self.lockin1.x1,
                "X2": self.lockin1.x2,
                "Y1": self.lockin1.y1,
                "Y2": self.lockin1.y2,
                "OOP_field_strength": field,
                "Xfield_avg": np.mean(xfields),
                "Xfield_std": np.std(xfields),
                "Yfield_avg": np.mean(yfields),
                "Yfield_std": np.std(yfields),
                "Zfield_avg": np.mean(zfields),
                "Zfield_std": np.std(zfields),
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
                    self.magnet.theta = theta*180./np.pi
                    while self.magnet.in_motion: # wait for all motion to finish
                        sleep(0.1)
                    for err in self.magnet.errors:
                        log.warning('%s'%err)

                    #Set field strength from vector sum of IP and OOP fields
                    field_vector_sum = np.sqrt(self.field_IP_strength**2 + field**2)
                    self.magnet.field = field_vector_sum
                    sleep(self.delay)

                    xfields = np.array([])
                    yfields = np.array([])
                    zfields = np.array([])
                    
                    for i in range(5):
                        sleep(self.delay)
                        xfields = np.append(xfields,self.get_Bx_zeroed())
                        yfields = np.append(yfields,self.get_By_zeroed())
                        zfields = np.append(zfields,self.get_Bz_zeroed())

                    log.info("Recording results")
                    self.emit('results', {
                        "X1": self.lockin1.x1,
                        "X2": self.lockin1.x2,
                        "Y1": self.lockin1.y1,
                        "Y2": self.lockin1.y2,
                        "OOP_field_strength": field,
                        "Xfield_avg": np.mean(xfields),
                        "Xfield_std": np.std(xfields),
                        "Yfield_avg": np.mean(yfields),
                        "Yfield_std": np.std(yfields),
                        "Zfield_avg": np.mean(zfields),
                        "Zfield_std": np.std(zfields),
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
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
