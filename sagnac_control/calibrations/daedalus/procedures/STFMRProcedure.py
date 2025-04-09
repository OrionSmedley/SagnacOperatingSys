import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.agilent import Agilent8257D
from ..custom_instruments import daedalusProjField, Keithley220
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class STFMRProcedure(Procedure):
    """
    Procedure for taking STFMR Measurements with the Daedalus setup
    """
    
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_strength_start = FloatParameter("Start Magnetic Field", units="T", default=0.)
    field_strength_end = FloatParameter("End Magnetic Field", units="T", default=0.1)
    field_strength_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)
    delay = FloatParameter("Delay", units="s", default=0.5)
    field_swap = BooleanParameter("Swap Field", default=True)

    rf_freq = FloatParameter("RF Frequency", units="GHz", default=12.0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    lockin_ac_gain = FloatParameter("Gain", units="dB", default=20.0)
    AM_freq = FloatParameter("AM Frequency", units='Hz', default=1713.0)
    lockin_phase = FloatParameter("Lockin Phase", units='deg', default=0.)
    lockin_sense_mode = Parameter("Lockin Sense Mode")

    sensitivity = FloatParameter("Lockin Sensitivity", units="V", default=0.01)
    time_constant = FloatParameter("Lockin Time Constant", units="s", default=0.5)

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("DC Bias Current", units='A', default=1e-4)

    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["X","Y","field_strength","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.rf_source = Agilent8257D("GPIB::19")
        self.rf_source.frequency = self.rf_freq*1e9
        self.rf_source.power = self.rf_power
        self.rf_source.enable_modulation()
        self.rf_source.config_amplitude_modulation(frequency=self.AM_freq,shape='sine',depth=100)
        self.rf_source.config_low_freq_out(source='internal',amplitude=3.)
        self.rf_source.enable()

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, atol=1e-3):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} deg")
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

        self.lockin = DSP7265("GPIB::12")
        self.lockin.set_voltage_mode()
        if self.lockin_sense_mode == 'A':
            self.lockin.setChannelAMode()
        elif self.lockin_sense_mode == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_mode == 'A-B':
            self.lockin.setDifferentialMode()
        self.lockin.gain = self.lockin_ac_gain
        self.lockin.time_constant = self.time_constant
        self.lockin.sensitivity = self.sensitivity
        self.lockin.harmonic = 1
        self.lockin.phase = self.lockin_phase
        self.lockin.reference = 'external front'
        self.lockin.voltage_input_device = 'FET'
        self.lockin.input_coupling = 'AC'

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info(f"Setting DC bias current to {self.dc_bias} A")
            self.bias_source.current = self.dc_bias
            log.info("Waiting 5 seconds to equilibrate")
            sleep(5)

    def execute(self):
        field_points = np.arange(self.field_strength_start,
                                 self.field_strength_end,
                                 self.field_strength_step)
        if self.field_strength_end not in field_points:
            field_points = np.append(field_points,self.field_strength_end)
        field_points = field_points[::-1] # reduce pole remnants
        if self.field_swap:
            field_points=np.concatenate((field_points, -1*field_points))

        num_progress = field_points.size

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info(f"Setting magnetic field to {field} T")
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
            log.info("Finished with scans. Shutting down instruments.")
            self.rf_source.power = -100
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class PHSTFMRProcedure(Procedure):
    """
    Procedure for taking STFMR Measurements with the Daedalus setup
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_strength_start = FloatParameter("Start Magnetic Field", units="T", default=0.)
    field_strength_end = FloatParameter("End Magnetic Field", units="T", default=0.1)
    field_strength_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)
    delay = FloatParameter("Delay", units="s", default=0.5)
    field_swap = BooleanParameter("Swap Field", default=True)

    rf_freq = FloatParameter("RF Frequency", units="GHz", default=12.0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    AM_freq = FloatParameter("AM Frequency", units='Hz', default=1713.0)


    lockin_phaseL = FloatParameter("Longitudinal Lockin Phase", units='deg', default=0.)
    sensitivityL = FloatParameter("Longitudinal Lockin Sensitivity", units="V", default=0.01)
    time_constantL = FloatParameter("Longitudinal Lockin Time Constant", units="s", default=0.5)
    lockin_ac_gainL = FloatParameter("Longitudinal Gain", units="dB", default=20.0)
    lockin_sense_modeL = Parameter("Longitudinal Lockin Sense Mode")
    
    lockin_phaseT = FloatParameter("Transverse Lockin Phase", units='deg', default=0.)
    sensitivityT = FloatParameter("Transverse Lockin Sensitivity", units="V", default=0.01)
    time_constantT = FloatParameter("Transverse Lockin Time Constant", units="s", default=0.5)
    lockin_ac_gainT = FloatParameter("Transverse Gain", units="dB", default=20.0)
    lockin_sense_modeT = Parameter("Transverse Lockin Sense Mode")

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("DC Bias Current", units='A', default=1e-4)

    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["X","Y","Xt","Yt", "field_strength","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.rf_freq*1e9
        self.rf_source.power = self.rf_power
        self.rf_source.enable_modulation()
        self.rf_source.config_amplitude_modulation(frequency=1713.0,shape='sine',depth=100) # parameters from UtilSweep
        self.rf_source.config_low_freq_out(source='internal',amplitude=3.) # parameters from UtilSweep
        self.rf_source.enable()

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, atol=1e-3):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} degrees")
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

        log.info(f"Setting magnetic field to maximum value of {self.field_strength_end} T")
        self.magnet.field = self.field_strength_end
        sleep(5)

        self.lockinL = DSP7265("GPIB::12")
        self.lockinL.set_voltage_mode()
        if self.lockin_sense_modeL == 'A':
            self.lockinL.setChannelAMode()
        elif self.lockin_sense_modeL == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_modeL == 'A-B':
            self.lockinL.setDifferentialMode()
        self.lockinL.time_constant = self.time_constantL
        self.lockinL.sensitivity = self.sensitivityL
        self.lockinL.harmonic = 1
        self.lockinL.phase = self.lockin_phaseL
        self.lockinL.reference = 'external front'
        self.lockinL.voltage_input_device = 'FET'
        self.lockinL.input_coupling = 'AC'
        self.lockinL.gain = self.lockin_ac_gainL

        self.lockinT = DSP7265("GPIB::11") # "secondary" lockin
        self.lockinT.set_voltage_mode()
        if self.lockin_sense_modeT == 'A':
            self.lockinT.setChannelAMode()
        elif self.lockin_sense_modeT == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_modeT == 'A-B':
            self.lockinT.setDifferentialMode()
        self.lockinT.time_constant = self.time_constantT
        self.lockinT.sensitivity = self.sensitivityT
        self.lockinT.harmonic = 1
        self.lockinT.phase = self.lockin_phaseT
        self.lockinT.reference = 'external front'
        self.lockinT.voltage_input_device = 'FET'
        self.lockinT.input_coupling = 'AC'
        self.lockinT.gain = self.lockin_ac_gainT

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info(f"Setting DC bias current to {self.dc_bias} A")
            self.bias_source.current = self.dc_bias
            log.info("Waiting 5 seconds to equilibrate")
            sleep(5)

    def execute(self):
        field_points = np.arange(self.field_strength_start,
                                 self.field_strength_end,
                                 self.field_strength_step)
        if self.field_strength_end not in field_points:
            field_points = np.append(field_points,self.field_strength_end)
        field_points = field_points[::-1] # reduce pole remnants
        if self.field_swap:
            field_points = np.concatenate((field_points, -1*field_points))

        num_progress = field_points.size

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field to %g T" % field)
            self.magnet.field = field
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockinL.x,
                "Y": self.lockinL.y,
                "Xt": self.lockinT.x,
                "Yt": self.lockinT.y,
                "field_strength": self.magnet.field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.rf_source.power = -100
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockinL.shutdown()
            self.lockinT.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class PHSTFMRAngProcedure(Procedure):
    """
    Procedure for taking STFMR Measurements with the Daedalus setup
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')

    field_strength = FloatParameter("Field Strength", units="T", default=0.1)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_azimuth_start = FloatParameter("Start Azimuthal Field", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Azimuthal Field", units="deg", default=355)
    field_azimuth_step = FloatParameter("Azimuthal Field Step", units="deg", default=5)
    delay = FloatParameter("Delay", units="s", default=0.5)

    rf_freq = FloatParameter("RF Frequency", units="GHz", default=12.0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    AM_freq = FloatParameter("AM Frequency", units='Hz', default=1713.0)


    lockin_phaseL = FloatParameter("Longitudinal Lockin Phase", units='deg', default=0.)
    sensitivityL = FloatParameter("Longitudinal Lockin Sensitivity", units="V", default=0.01)
    time_constantL = FloatParameter("Longitudinal Lockin Time Constant", units="s", default=0.5)
    lockin_ac_gainL = FloatParameter("Longitudinal Gain", units="dB", default=20.0)
    lockin_sense_modeL = Parameter("Longitudinal Lockin Sense Mode")
    
    lockin_phaseT = FloatParameter("Transverse Lockin Phase", units='deg', default=0.)
    sensitivityT = FloatParameter("Transverse Lockin Sensitivity", units="V", default=0.01)
    time_constantT = FloatParameter("Transverse Lockin Time Constant", units="s", default=0.5)
    lockin_ac_gainT = FloatParameter("Transverse Gain", units="dB", default=20.0)
    lockin_sense_modeT = Parameter("Transverse Lockin Sense Mode")

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("DC Bias Current", units='A', default=1e-4)

    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["X","Y","Xt","Yt", "field_azimuth","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.rf_freq*1e9
        self.rf_source.power = self.rf_power
        self.rf_source.enable_modulation()
        self.rf_source.config_amplitude_modulation(frequency=1713.0,shape='sine',depth=100) # parameters from UtilSweep
        self.rf_source.config_low_freq_out(source='internal',amplitude=3.) # parameters from UtilSweep
        self.rf_source.enable()

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
        # Set to desired field
        log.info("setting magnet field strength to %g T" % self.field_strength)
        self.magnet.field = self.field_strength

        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        log.info(f"setting magnet azimuthal angle to {self.field_azimuth_start} degrees")
        self.magnet.phi = self.field_azimuth_start
        for err in self.magnet.errors:
            log.warning('%s'%err)
        while self.magnet.in_motion:
            sleep(0.1)
        sleep(self.delay)

        sleep(20)

        self.lockinL = DSP7265("GPIB::12")
        self.lockinL.set_voltage_mode()
        if self.lockin_sense_modeL == 'A':
            self.lockinL.setChannelAMode()
        elif self.lockin_sense_modeL == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_modeL == 'A-B':
            self.lockinL.setDifferentialMode()
        self.lockinL.time_constant = self.time_constantL
        self.lockinL.sensitivity = self.sensitivityL
        self.lockinL.harmonic = 1
        self.lockinL.phase = self.lockin_phaseL
        self.lockinL.reference = 'external front'
        self.lockinL.voltage_input_device = 'FET'
        self.lockinL.input_coupling = 'AC'
        self.lockinL.gain = self.lockin_ac_gainL

        self.lockinT = DSP7265("GPIB::11") # "secondary" lockin
        self.lockinT.set_voltage_mode()
        if self.lockin_sense_modeT == 'A':
            self.lockinT.setChannelAMode()
        elif self.lockin_sense_modeT == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_modeT == 'A-B':
            self.lockinT.setDifferentialMode()
        self.lockinT.time_constant = self.time_constantT
        self.lockinT.sensitivity = self.sensitivityT
        self.lockinT.harmonic = 1
        self.lockinT.phase = self.lockin_phaseT
        self.lockinT.reference = 'external front'
        self.lockinT.voltage_input_device = 'FET'
        self.lockinT.input_coupling = 'AC'
        self.lockinT.gain = self.lockin_ac_gainT

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info(f"Setting DC bias current to {self.dc_bias} A")
            self.bias_source.current = self.dc_bias
            log.info("Waiting 5 seconds to equilibrate")
            sleep(5)

    def execute(self):
        angles = np.arange(self.field_azimuth_start,
                                 self.field_azimuth_end,
                                 self.field_azimuth_step)
        if self.field_azimuth_end not in angles:
            angles = np.append(angles,self.field_azimuth_end)

        num_progress = angles.size

        start_time = time()

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting angle to {angle} deg")
            self.magnet.phi = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockinL.x,
                "Y": self.lockinL.y,
                "Xt": self.lockinT.x,
                "Yt": self.lockinT.y,
                "field_azimuth": angle,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.rf_source.power = -100
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockinL.shutdown()
            self.lockinT.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)


class STFMRProcedure_freq(Procedure):
    """
    Procedure for taking STFMR Measurements with the Daedalus setup
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    freq_start = FloatParameter("Start Frequency", units="GHz", default=7)
    freq_end = FloatParameter("End Magnetic Field", units="GHz", default=8)
    freq_step = FloatParameter("Magnetic Field Step", units="GHz", default=0.05)
    delay = FloatParameter("Delay", units="s", default=0.5)

    field_strength = FloatParameter("Field Strength", units="T", default=0.1)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    lockin_ac_gain = FloatParameter("Gain", units="dB", default=40.0)

    sensitivity = FloatParameter("Lockin Sensitivity", units="V", default=0.01)
    time_constant = FloatParameter("Lockin Time Constant", units="s", default=0.5)

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("DC Bias Current", units='A', default=1e-4)

    queued_time = Parameter('Time Queued')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ["X","Y","rf_freq","elapsed_time"]

    def startup(self):
        # TODO: Look for more setup stuff to be done.
        log.info("Connecting and configuring the instruments")

        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.freq_start*1e9
        self.rf_source.power = self.rf_power
        self.rf_source.enable_modulation()
        self.rf_source.config_amplitude_modulation(frequency=1713.0,shape='sine',depth=100) # parameters from UtilSweep
        self.rf_source.config_low_freq_out(source='internal',amplitude=3.) # parameters from UtilSweep
        self.rf_source.enable()

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, atol=1e-3):
            log.info("setting magnet azimuthal orientation to %g degrees" % self.field_azimuth)
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info("setting magnet polar orientation to %g degrees" % self.field_polar)
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

        log.info("Setting magnetic field to maximum value of %g T"%self.field_strength_end)
        self.magnet.field = self.field_strength_end
        sleep(5)

        self.lockin = DSP7265("GPIB::12")
        self.lockin.set_voltage_mode()
        self.lockin.setChannelAMode()
        self.lockin.gain = self.lockin_ac_gain
        self.lockin.time_constant = self.time_constant
        self.lockin.sensitivity = self.sensitivity
        self.lockin.harmonic = 1
        self.lockin.phase = 0.
        self.lockin.reference = 'external front'
        self.lockin.voltage_input_device = 'FET'
        self.lockin.input_coupling = 'AC'

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info("Setting DC bias current to %g A"%self.dc_bias)
            self.bias_source.current = self.dc_bias
            log.info("Waiting 10 seconds to equilibrate")
            sleep(5)


    def execute(self):
        freq_points = np.arange(self.freq_start,
                                 self.freq_end,
                                 self.freq_step)
        if self.freq_end not in freq_points:
            freq_points = np.append(freq_points,self.freq_end)
        num_progress = freq_points.size

        start_time = time()

        # Eliminate pole remnants/make measurements reproducible
        voltage_pole_elim = np.sign(self.field_strength) * 10
        log.info("Setting magnet voltage to %g V to eliminate pole remnants"%voltage_pole_elim)
        self.magnet.volts = voltage_pole_elim
        self.magnet.field = self.field_strength
        log.info("Setting field to %g T"%self.magnet.field)
        for progress_iterator, freq in enumerate(freq_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting rf frequency to %g GHz" % freq)
            self.rf_source.frequency = freq*1e9
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockin.x,
                "Y": self.lockin.y,
                "rf_freq": self.rf_source.frequency,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.rf_source.power = -100
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockin.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)


class PHSTFMRProcedureContinuousField(Procedure):
    """
    Procedure for taking STFMR Measurements with the Daedalus setup
    """

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_strength_start = FloatParameter("Start Magnetic Field", units="T", default=0.)
    field_strength_end = FloatParameter("End Magnetic Field", units="T", default=0.1)
    field_strength_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)
    delay = FloatParameter("Delay", units="s", default=0.5)
    field_swap = BooleanParameter("Swap Field", default=True)

    rf_freq = FloatParameter("RF Frequency", units="GHz", default=12.0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    AM_freq = FloatParameter("AM Frequency", units='Hz', default=1713.0)


    lockin_phaseL = FloatParameter("Longitudinal Lockin Phase", units='deg', default=0.)
    sensitivityL = FloatParameter("Longitudinal Lockin Sensitivity", units="V", default=0.01)
    time_constantL = FloatParameter("Longitudinal Lockin Time Constant", units="s", default=0.5)
    lockin_ac_gainL = FloatParameter("Longitudinal Gain", units="dB", default=20.0)
    lockin_sense_modeL = Parameter("Longitudinal Lockin Sense Mode")
    
    lockin_phaseT = FloatParameter("Transverse Lockin Phase", units='deg', default=0.)
    sensitivityT = FloatParameter("Transverse Lockin Sensitivity", units="V", default=0.01)
    time_constantT = FloatParameter("Transverse Lockin Time Constant", units="s", default=0.5)
    lockin_ac_gainT = FloatParameter("Transverse Gain", units="dB", default=20.0)
    lockin_sense_modeT = Parameter("Transverse Lockin Sense Mode")

    use_bias = BooleanParameter("Use Bias Current", default=False)
    dc_bias = FloatParameter("DC Bias Current", units='A', default=1e-4)

    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["X","Y","Xt","Yt", "field_strength","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.rf_freq*1e9
        self.rf_source.power = self.rf_power
        self.rf_source.enable_modulation()
        self.rf_source.config_amplitude_modulation(frequency=1713.0,shape='sine',depth=100) # parameters from UtilSweep
        self.rf_source.config_low_freq_out(source='internal',amplitude=3.) # parameters from UtilSweep
        self.rf_source.enable()

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, atol=1e-3):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} degrees")
            self.magnet.phi = self.field_azimuth
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

        log.info(f"Setting magnetic field to maximum value of {self.field_strength_end} T")
        self.magnet.field = self.field_strength_end
        sleep(5)

        self.lockinL = DSP7265("GPIB::12")
        self.lockinL.set_voltage_mode()
        if self.lockin_sense_modeL == 'A':
            self.lockinL.setChannelAMode()
        elif self.lockin_sense_modeL == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_modeL == 'A-B':
            self.lockinL.setDifferentialMode()
        self.lockinL.time_constant = self.time_constantL
        self.lockinL.sensitivity = self.sensitivityL
        self.lockinL.harmonic = 1
        self.lockinL.phase = self.lockin_phaseL
        self.lockinL.reference = 'external front'
        self.lockinL.voltage_input_device = 'FET'
        self.lockinL.input_coupling = 'AC'
        self.lockinL.gain = self.lockin_ac_gainL

        self.lockinT = DSP7265("GPIB::11") # "secondary" lockin
        self.lockinT.set_voltage_mode()
        if self.lockin_sense_modeT == 'A':
            self.lockinT.setChannelAMode()
        elif self.lockin_sense_modeT == '-B':
            # TODO: implement this in instrument driver
            raise NotImplementedError("Lockin -B mode not supported yet!")
        elif self.lockin_sense_modeT == 'A-B':
            self.lockinT.setDifferentialMode()
        self.lockinT.time_constant = self.time_constantT
        self.lockinT.sensitivity = self.sensitivityT
        self.lockinT.harmonic = 1
        self.lockinT.phase = self.lockin_phaseT
        self.lockinT.reference = 'external front'
        self.lockinT.voltage_input_device = 'FET'
        self.lockinT.input_coupling = 'AC'
        self.lockinT.gain = self.lockin_ac_gainT

        if self.use_bias:
            self.bias_source = Keithley220("GPIB::3")
            self.bias_source.enable()
            log.info(f"Setting DC bias current to {self.dc_bias} A")
            self.bias_source.current = self.dc_bias
            log.info("Waiting 5 seconds to equilibrate")
            sleep(5)

    def execute(self):
        field_points = np.arange(self.field_strength_start,
                                 self.field_strength_end,
                                 self.field_strength_step)
        if self.field_strength_end not in field_points:
            field_points = np.append(field_points,self.field_strength_end)
        # field_points = field_points[::-1] reduce pole remnants
        if self.field_swap:
            field_points = np.concatenate((field_points[::-1], -1*field_points))

        num_progress = field_points.size

        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field to %g T" % field)
            self.magnet.field = field
            sleep(self.delay)
            log.info("Recording results")
            self.emit('results', {
                "X": self.lockinL.x,
                "Y": self.lockinL.y,
                "Xt": self.lockinT.x,
                "Yt": self.lockinT.y,
                "field_strength": self.magnet.field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.rf_source.power = -100
            self.magnet.shutdown()
            for err in self.magnet.errors:
                log.warning('%s'%err)
            self.lockinL.shutdown()
            self.lockinT.shutdown()
            if self.use_bias:
                self.bias_source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
