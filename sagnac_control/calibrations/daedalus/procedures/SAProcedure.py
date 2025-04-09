import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename
from pymeasure.instruments.agilent import Agilent8257D
from ..custom_instruments import daedalusProjField
from pymeasure.experiment import Procedure
from pymeasure.adapters import DAQmxAdapter
import numpy as np
from time import sleep, time
try:
    from pymeasure.instruments.agilent import Agilent8563E
except ImportError as e:
    log.warning("Could not load instruments for the procedure class")
    #log.exception(e)




class SAFreqProcedure(Procedure):

    sample_name = Parameter('Sample')
    station_name = Parameter('Station Name')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_strength = FloatParameter("Start Magnetic Field", units="T", default=0.)
    # field_strength_end = FloatParameter("End Magnetic Field", units="T", default=0.1)
    # field_strength_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations/proj_field')
    delay = FloatParameter("Delay", units="s", default=0.5)
    #field_swap = BooleanParameter("Swap Field", default=False)

    AM_freq = FloatParameter('AM modulation', units='Hz', default=0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    rf_frequency_start = FloatParameter('Initial RF frequency', units='Hz', default=1,maximum=20e9)
    rf_frequency_end = FloatParameter('Final RF frequency', units='Hz', default=10,maximum=20e9)
    rf_frequency_step = FloatParameter('RF frequency step', units='Hz', default=1,maximum=20e9)
    #start_frequency_multiplier = FloatParameter('start_frequency_multiplier', default=1e9)
    #end_frequency_multiplier = FloatParameter('end_frequency_multiplier', default=1e9)

    # reference_level = FloatParameter('reference_level', units='dBm', default=0)
    # resolution_bandwidth = FloatParameter('resolution_bandwidth', units='Hz', default=1)
    # video_bandwidth = FloatParameter('video_bandwidth', units='Hz', default=1)
    #sweep_time = FloatParameter('sweep_time', units='sec', default=1)
    span = FloatParameter('Span', units='Hz', default=1,maximum=20e9)
    zero_span = BooleanParameter('Zero Span', default =True)
    resolution_bandwidth = FloatParameter('Resolution Bandwidth', units='Hz', default=1,maximum=20e9)
    video_bandwidth = FloatParameter('video Bandwidth', units='Hz', default=1,maximum=20e9)
    # log_scale = IntegerParameter('log_scale', units='dB', default=0)

    start_time = Parameter('Start time')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ['rf_freq','log_rf_freq', 'A', 'A_lin', "elapsed_time"]


    def startup(self):

        log.info("Initializing instruments")
        self.sa = Agilent8563E('GPIB::20',timeout=25000) # TODO: GPIB address
        self.sa.default_config(self.resolution_bandwidth,self.video_bandwidth)

        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.rf_frequency_start
        self.rf_source.power = self.rf_power
        if self.AM_freq == 0:
            self.rf_source.disable_modulation()
        else:
            self.rf_source.enable_modulation()
            self.rf_source.config_amplitude_modulation(
                            frequency=self.AM_freq,shape='sine',depth=100) # parameters from UtilSweep
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

        log.info("Setting magnetic field to %g T" %self.field_strength)
        self.magnet.field = self.field_strength
        sleep(5)

        log.info('finished Initializing')

        sleep(0.1)

    def execute(self):
        start_time = time()
        log.info('beginning the scan')

        freq_points = np.arange(self.rf_frequency_start,
                                 self.rf_frequency_end,
                                 self.rf_frequency_step)
        if self.rf_frequency_end not in freq_points:
            freq_points = np.append(freq_points,self.rf_frequency_end)


        num_progress = freq_points.size
        for progress_iterator, f in enumerate(freq_points):
            log.info("Setting rf frequency to %f Hz"%f)
            self.rf_source.frequency = f
            self.sa.center_frequency = f
            sleep(self.delay)
            if self.zero_span:
                A = self.sa.zero_span_scan(f)
            else:
                A = self.sa.scan(f, self.span) # array
                window_points = np.linspace(f-self.span,f+self.span,601)
                A = 1e-3 * 10**(A/10.) # convert to linear
                A = np.trapz(A,x=window_points)/(2*self.span) #integrate
                A = 10*np.log10(A/1e-3) # convert back to dBm
            self.emit('progress',int(100*progress_iterator/num_progress))
            log.info("Recording results")
            self.emit('results', {
                "A": A,
                "A_lin": 1e-3*10**(A/10.),
                "rf_freq": f,
                "log_rf_freq": np.log10(f),
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
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class SAFieldProcedure(Procedure):

    sample_name = Parameter('Sample')
    station_name = Parameter('Station Name')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_strength_start = FloatParameter("Start Magnetic Field", units="T", default=0.)
    field_strength_end = FloatParameter("End Magnetic Field", units="T", default=0.1)
    field_strength_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations/proj_field')
    delay = FloatParameter("Delay", units="s", default=0.5)
    field_swap = BooleanParameter("Swap Field", default=False)

    AM_freq = FloatParameter('AM modulation', units='Hz', default=0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    rf_frequency_start = FloatParameter('Initial RF frequency', units='Hz', default=1,maximum=20e9)
    # rf_frequency_end = FloatParameter('Final RF frequency', units='Hz', default=10,maximum=20e9)
    # rf_frequency_step = FloatParameter('RF frequency step', units='Hz', default=1,maximum=20e9)
    #start_frequency_multiplier = FloatParameter('start_frequency_multiplier', default=1e9)
    #end_frequency_multiplier = FloatParameter('end_frequency_multiplier', default=1e9)

    # reference_level = FloatParameter('reference_level', units='dBm', default=0)
    # resolution_bandwidth = FloatParameter('resolution_bandwidth', units='Hz', default=1)
    # video_bandwidth = FloatParameter('video_bandwidth', units='Hz', default=1)
    #sweep_time = FloatParameter('sweep_time', units='sec', default=1)
    span = FloatParameter('Span', units='Hz', default=1,maximum=20e9)
    zero_span = BooleanParameter('Zero Span', default =True)
    resolution_bandwidth = FloatParameter('Resolution Bandwidth', units='Hz', default=1,maximum=20e9)
    video_bandwidth = FloatParameter('video Bandwidth', units='Hz', default=1,maximum=20e9)
    # log_scale = IntegerParameter('log_scale', units='dB', default=0)

    start_time = Parameter('Start time')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ['field_strength', 'A', 'A_lin', "elapsed_time"]


    def startup(self):

        log.info("Initializing instruments")
        self.sa = Agilent8563E('GPIB::20',timeout=25000) # TODO: GPIB address
        self.sa.default_config(self.resolution_bandwidth,self.video_bandwidth)
        self.sa.center_frequency = self.rf_frequency_start


        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.rf_frequency_start
        self.rf_source.power = self.rf_power
        if self.AM_freq == 0:
            self.rf_source.disable_modulation()
        else:
            self.rf_source.enable_modulation()
            self.rf_source.config_amplitude_modulation(
                            frequency=self.AM_freq,shape='sine',depth=100) # parameters from UtilSweep
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

        log.info("Setting magnetic field to %g T" %self.field_strength)
        self.magnet.field = self.field_strength
        sleep(5)

        log.info('finished Initializing')

        sleep(0.1)

    def execute(self):
        start_time = time()
        log.info('beginning the scan')

        field_points = np.arange(self.field_strength_start,
                                 self.field_strength_end,
                                 self.field_strength_step)
        if self.field_strength_end not in field_points:
            field_points = np.append(field_points,self.field_strength_end)
        field_points = field_points[::-1]
        if self.field_swap:
            field_points = np.append(field_points,-field_points)

        num_progress = field_points.size
        for progress_iterator, b in enumerate(field_points):
            log.info("Setting field_strength to %f T"%b)
            self.magnet.field = b
            sleep(self.delay)
            if self.zero_span:
                A = self.sa.zero_span_scan(self.rf_frequency_start)
            else:
                A = self.sa.scan(self.rf_frequency_start, self.span) # array
                window_points = np.linspace(self.rf_frequency_start-self.span,self.rf_frequency_start+self.span,601)
                A = 1e-3 * 10**(A/10.) # convert to linear
                A = np.trapz(A,x=window_points)/(2*self.span) #integrate
                A = 10*np.log10(A/1e-3) # convert back to dBm
            self.emit('progress',int(100*progress_iterator/num_progress))
            log.info("Recording results")
            self.emit('results', {
                "A": A,
                "A_lin": 1e-3*10**(A/10.),
                "field_strength": b,
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
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class SAAngProcedure(Procedure):

    sample_name = Parameter('Sample')
    station_name = Parameter('Station Name')

    field_azimuth_start = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Magnetic Field Azimuthal Angle", units="deg", default=360)
    field_azimuth_step = FloatParameter("Magnetic Field Azimuthal Angle Step", units="deg", default=1)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_strength = FloatParameter("Start Magnetic Field", units="T", default=0.)


    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations/proj_field')
    delay = FloatParameter("Delay", units="s", default=0.5)
    field_swap = BooleanParameter("Swap Field", default=False)

    AM_freq = FloatParameter('AM modulation', units='Hz', default=0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    rf_frequency_start = FloatParameter('Initial RF frequency', units='Hz', default=1,maximum=20e9)
    # rf_frequency_end = FloatParameter('Final RF frequency', units='Hz', default=10,maximum=20e9)
    # rf_frequency_step = FloatParameter('RF frequency step', units='Hz', default=1,maximum=20e9)
    #start_frequency_multiplier = FloatParameter('start_frequency_multiplier', default=1e9)
    #end_frequency_multiplier = FloatParameter('end_frequency_multiplier', default=1e9)

    # reference_level = FloatParameter('reference_level', units='dBm', default=0)
    # resolution_bandwidth = FloatParameter('resolution_bandwidth', units='Hz', default=1)
    # video_bandwidth = FloatParameter('video_bandwidth', units='Hz', default=1)
    #sweep_time = FloatParameter('sweep_time', units='sec', default=1)
    span = FloatParameter('Span', units='Hz', default=1,maximum=20e9)
    zero_span = BooleanParameter('Zero Span', default =True)
    resolution_bandwidth = FloatParameter('Resolution Bandwidth', units='Hz', default=1,maximum=20e9)
    video_bandwidth = FloatParameter('video Bandwidth', units='Hz', default=1,maximum=20e9)
    # log_scale = IntegerParameter('log_scale', units='dB', default=0)

    start_time = Parameter('Start time')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ['field_azimuth', 'A', 'A_lin', "elapsed_time"]


    def startup(self):

        log.info("Initializing instruments")
        self.sa = Agilent8563E('GPIB::20',timeout=25000) # TODO: GPIB address
        self.sa.default_config(self.resolution_bandwidth,self.video_bandwidth)
        self.sa.center_frequency = self.rf_frequency_start


        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.rf_frequency_start
        self.rf_source.power = self.rf_power
        if self.AM_freq == 0:
            self.rf_source.disable_modulation()
        else:
            self.rf_source.enable_modulation()
            self.rf_source.config_amplitude_modulation(
                            frequency=self.AM_freq,shape='sine',depth=100) # parameters from UtilSweep
            self.rf_source.config_low_freq_out(source='internal',amplitude=3.) # parameters from UtilSweep
        self.rf_source.enable()

        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth, atol=1e-3):
            log.info("setting magnet azimuthal orientation to %g degrees" % self.field_azimuth_start)
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

        log.info("Setting magnetic field to %g T" %self.field_strength)
        self.magnet.field = self.field_strength
        sleep(5)

        log.info('finished Initializing')

        sleep(0.1)

    def execute(self):
        start_time = time()
        log.info('beginning the scan')

        ang_points = np.arange(self.field_azimuth_start,
                                 self.field_azimuth_end,
                                 self.field_azimuth_step)
        if self.field_azimuth_end not in ang_points:
            ang_points = np.append(ang_points,self.field_azimuth_end)

        num_progress = ang_points.size
        for progress_iterator, ang in enumerate(ang_points):
            log.info("Setting field_strength to %f T"%b)
            self.magnet.phi = ang
            sleep(self.delay)
            if self.zero_span:
                A = self.sa.zero_span_scan(self.rf_frequency_start)
            else:
                A = self.sa.scan(self.rf_frequency_start, self.span) # array
                window_points = np.linspace(self.rf_frequency_start-self.span,self.rf_frequency_start+self.span,601)
                A = 1e-3 * 10**(A/10.) # convert to linear
                A = np.trapz(A,x=window_points)/(2*self.span) #integrate
                A = 10*np.log10(A/1e-3) # convert back to dBm
            self.emit('progress',int(100*progress_iterator/num_progress))
            log.info("Recording results")
            self.emit('results', {
                "A": A,
                "A_lin": 1e-3*10**(A/10.),
                "field_azimuth": ang,
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
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class SA2dFreqProcedure(Procedure):

    sample_name = Parameter('Sample')
    station_name = Parameter('Station Name')

    field_azimuth = FloatParameter("Magnetic Field Azimuthal Angle", units="deg", default=0.)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)

    field_strength = FloatParameter("Start Magnetic Field", units="T", default=0.)
    # field_strength_end = FloatParameter("End Magnetic Field", units="T", default=0.1)
    # field_strength_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)

    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations/proj_field')
    delay = FloatParameter("Delay", units="s", default=0.5)
    #field_swap = BooleanParameter("Swap Field", default=False)

    AM_freq = FloatParameter('AM modulation', units='Hz', default=0)
    rf_power = FloatParameter("RF Power", units="dBmW", default=18.0)
    rf_frequency_start = FloatParameter('Initial RF frequency', units='Hz', default=1,maximum=20e9)
    rf_frequency_end = FloatParameter('Final RF frequency', units='Hz', default=10,maximum=20e9)
    rf_frequency_step = FloatParameter('RF frequency step', units='Hz', default=1,maximum=20e9)
    #start_frequency_multiplier = FloatParameter('start_frequency_multiplier', default=1e9)
    #end_frequency_multiplier = FloatParameter('end_frequency_multiplier', default=1e9)

    resolution_bandwidth = FloatParameter('resolution bandwidth', units='Hz', default=1,maximum=20e9)
    video_bandwidth = FloatParameter('video bandwidth', units='Hz', default=1,maximum=20e9)

    rf_freq_start = FloatParameter('Initial RF frequency', units='Hz', default=1,maximum=20e9)
    rf_freq_end = FloatParameter('Final RF frequency', units='Hz', default=10,maximum=20e9)
    rf_freq_step = FloatParameter('RF frequency step', units='Hz', default=1,maximum=20e9)
    freq_SA_start = FloatParameter('Initial SA frequency', units='Hz', default=1,maximum=20e9)
    freq_SA_end = FloatParameter('Final SA frequency', units='Hz', default=10,maximum=20e9)
    freq_SA_step = FloatParameter('SA frequency step', units='Hz', default=1,maximum=20e9)
        # reference_level = FloatParameter('reference_level', units='dBm', default=0)
    # resolution_bandwidth = FloatParameter('resolution_bandwidth', units='Hz', default=1)
    # video_bandwidth = FloatParameter('video_bandwidth', units='Hz', default=1)
    #sweep_time = FloatParameter('sweep_time', units='sec', default=1)
    span = FloatParameter('span', units='Hz', default = 0, maximum =20e9)
    full_scan = BooleanParameter('Full Scan', default = False)
    # log_scale = IntegerParameter('log_scale', units='dB', default=0)

    start_time = Parameter('Start time')

    # Will only mess with field and shutting down instruments if these are the
    # first or last things in a series. Need both to be true if only a single
    # one is done though!
    first = True
    last = True

    DATA_COLUMNS = ['rf_freq','log_rf_freq', 'freq_SA','log_freq_SA', 'A','A_lin', "elapsed_time"]


    def startup(self):

        log.info("Initializing instruments")
        self.sa = Agilent8563E('GPIB::20',timeout=25000) # TODO: GPIB address
        self.sa.start_frequency = int(self.rf_frequency_start)
        self.sa.stop_frequency = int(self.rf_frequency_end)
        # self.sa.reference_level = self.reference_level
        #self.sa.resolution_bandwidth = self.resolution_bandwidth
        #self.sa.video_bandwidth = self.video_bandwidth
        #self.sa.sweep_time = self.sweep_time
        #self.sa.log_scale = self.log_scale
        #self.sa.aunits = 'dBm' #dummy units to activate setter
        self.sa.default_config(self.resolution_bandwidth,self.video_bandwidth)
        self.sa.fixed_window(
                int(self.rf_frequency_start),
                int(self.rf_frequency_end),
                int(self.resolution_bandwidth),
                int(self.video_bandwidth)
        )

        self.rf_source = Agilent8257D("GPIB::19") # checked from utilsweep
        self.rf_source.frequency = self.rf_frequency_start
        self.rf_source.power = self.rf_power
        if self.AM_freq == 0:
            self.rf_source.disable_modulation()
        else:
            self.rf_source.enable_modulation()
            self.rf_source.config_amplitude_modulation(
                            frequency=self.AM_freq,shape='sine',depth=100) # parameters from UtilSweep
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

        log.info("Setting magnetic field to %g T" %self.field_strength)
        self.magnet.field = self.field_strength
        sleep(5)

        log.info('finished Initializing')

        sleep(0.1)

    def execute(self):
        start_time = time()
        log.info('beginning the scan')

        freq_points = np.arange(self.rf_frequency_start,
                                 self.rf_frequency_end,
                                 self.rf_frequency_step)
        if self.rf_frequency_end not in freq_points:
            freq_points = np.append(freq_points,self.rf_frequency_end)

        if self.full_scan:
            window_points = np.linspace(self.rf_frequency_start,
                                 self.rf_frequency_end,
                                 601) # spectrum analyzer always outputs 601 points

        num_progress = freq_points.size
        progress_iterator = 0
        for progress_iterator, f in enumerate(freq_points):
            log.info("Setting input frequency to %f Hz"%f)
            self.rf_source.frequency = f
            sleep(self.delay)
            if self.full_scan:
                A = self.sa.fixed_scan()
            else:
                A = self.sa.scan(f,self.span)
                window_points = np.linspace(f - self.span,
                                         f + self.span,
                                         601)
            self.emit('progress',int(100*progress_iterator/num_progress))
            log.info("Recording results")
            for j in range(601):
                self.emit('results', {
                    "A": A[j],
                    "A_lin": 1e-3*10**(A[j]/10.),
                    "rf_freq": f,
                    "log_rf_freq": np.log10(f),
                    "freq_SA": window_points[j],
                    "log_freq_SA": np.log10(window_points[j]),
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
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
