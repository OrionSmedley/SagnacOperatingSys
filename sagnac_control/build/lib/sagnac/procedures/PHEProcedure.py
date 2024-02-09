import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.zurich import HF2LI
from ..custom_instruments import daedalusProjField
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class sagnacPHEProcedure(Procedure):
    """
    Procedure for taking PHE Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    current_frequency = FloatParameter("Applied Sample Voltage frequency", units="kHz", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    applied_field = FloatParameter("Applied Magnetic Field", units="T", default=0.1)
    field_azimuth_start = FloatParameter("Field Azimuth start", units="deg", default=0)
    field_azimuth_end = FloatParameter("Field Azimuth stop", units="deg", default=170)
    field_azimuth_step = FloatParameter("Field Azimuth step", units="deg", default=1)
    field_polar = FloatParameter("Field Polar", units="deg", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","Ratio","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2","field_azimuth","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        log.info("Connecting to the magnet")
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        # self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
        self.lockin.set_vout(1,6,self.applied_voltage/10*np.sqrt(2)) #using output 7
        # Signal Inputs
        # Input channel 1
        # self.lockin.set_range(0, self.input_range)
        # self.lockin.set_ac_coupling(0,True)
        # self.lockin.set_imp50(0,self.imp50)
        # Input channel 2
        # self.lockin.set_range(1, self.input_range)
        # self.lockin.set_ac_coupling(1,True)
        # self.lockin.set_imp50(1,self.imp50)
        
        # Oscillators
        # self.lockin.set_osc_freq(0,self.f_eom)
        # self.lockin.set_osc_freq(1,self.f_eom - self.current_frequency)
        # self.lockin.set_osc_freq(2,2*self.f_eom - self.current_frequency)
        # self.lockin.set_osc_freq(3,self.current_frequency)
        # self.lockin.set_osc_freq(4,self.current_frequency)

        # Demodulators
        # self.lockin.set_osc_select(0,0)
        # self.lockin.set_harmonic(0,1)
        # self.lockin.set_phase(0,0)
        # self.lockin.set_filter_order(0,self.first_harm_order)
        # self.lockin.set_tc(0,self.first_harm_tc)
        # self.lockin.set_enable_demod(0,1)

        # self.lockin.set_osc_select(1,0)
        # self.lockin.set_harmonic(1,2)
        # self.lockin.set_phase(1,0)
        # self.lockin.set_filter_order(1,self.second_harm_order)
        # self.lockin.set_tc(1,self.second_harm_tc)
        # self.lockin.set_enable_demod(1,1)

        # self.lockin.set_osc_select(2,1)
        # self.lockin.set_harmonic(2,1)
        # self.lockin.set_phase(2,0)
        # self.lockin.set_filter_order(2,self.first_harm_order)
        # self.lockin.set_tc(2,self.first_harm_tc)
        # self.lockin.set_enable_demod(2,1)

        # self.lockin.set_osc_select(3,2)
        # self.lockin.set_harmonic(3,1)
        # self.lockin.set_phase(3,0)
        # self.lockin.set_filter_order(3,self.second_harm_order)
        # self.lockin.set_tc(3,self.first_harm_tc)
        # self.lockin.set_enable_demod(3,1)

        # self.lockin.set_osc_select(4,3)
        # self.lockin.set_harmonic(4,1)
        # self.lockin.set_phase(4,0)
        # self.lockin.set_filter_order(4,self.second_harm_order)
        # self.lockin.set_tc(4,self.first_harm_tc)
        # self.lockin.set_enable_demod(4,1)

        # the current output demod
        # self.lockin.set_osc_select(5,4)
        # self.lockin.set_harmonic(5,1)
        # self.lockin.set_phase(5,0)
        # self.lockin.set_filter_order(5,self.second_harm_order)
        # self.lockin.set_tc(5,self.second_harm_tc)
        # self.lockin.set_enable_demod(4,1)


        # output 1
        # self.lockin.set_outrange(0,1)
        # self.lockin.set_vout(0,0,self.eom_voltage)
        # self.lockin.set_enable_output(0,0,1)
        # self.lockin.set_offset(0,0)
        # self.lockin.set_sigon(0,1)

        # output 2
        # self.lockin.set_outrange(1,10)
        # self.lockin.set_vout(1,5,self.applied_voltage/10.)
        # self.lockin.set_enable_output(1,5,1)
        # self.lockin.set_offset(1,0)
        # self.lockin.set_sigon(1,1)

        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

    def execute(self):
        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end,
                           self.field_azimuth_step)
        if self.field_azimuth_end not in angles:
            angles = np.append(angles,self.field_azimuth_end)

        if self.saturate:
            # ensure we have gotten to the phi we want
            while not np.isclose(self.magnet.phi, self.saturating_field_azimuth, atol=1e-3):
                log.info(f"setting magnet azimuthal orientation to {self.saturating_field_azimuth} deg")
                self.magnet.phi = self.saturating_field_azimuth
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
            # NOTE: in the future will probably want to check that we have actually reached
            # the theta value we set it to.
            log.info(f"setting magnet polar orientation to {self.saturating_field_polar} degrees")
            self.magnet.theta = self.saturating_field_polar
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            log.info("Setting the Saturating Field")
            self.magnet.set_vector_field(self.saturating_field,
                                         phi=self.saturating_field_azimuth, 
                                         theta=self.saturating_field_polar)
            log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")
            sleep(self.settling)

            self.magnet.volts = 0
        
        self.magnet.phi = self.field_azimuth_start
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth_start, atol=1e-3):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth_start} deg")
            self.magnet.phi = self.field_azimuth_start
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
        log.info("Setting Field")
        self.magnet.field = self.applied_field
        log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")

        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        log.info("Waiting 5x settling time to equilibrate")
        sleep(self.settling*5)

        num_progress = angles.size
        start_time = time()

        for progress_iterator, ang in enumerate(angles):
            self.emit("progress", 100*progress_iterator/num_progress)
            self.magnet.phi = ang
            log.info(f"Setting Magnetic azimuth to {ang:.1f} deg")
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            
            # self.lockin.sync() # clears buffer since field has changed
            # sleep(self.settling)
            # self.lockin.sync()
            # dat = self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False)
            log.info("Recording results")

            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, #np.arctan(J2J1*np.sign(larger_1)*R1/R2)/2,
                "Ratio": dat[3]['x']/dat[5]['y'], #np.sign(larger_1)*R1/R2,
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y']/2,
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "TX1": dat[0]['x'],#/(self.amp_gain/2),
                "TY1": dat[0]['y'],#/(self.amp_gain/2),
                "TX2": dat[1]['x'],#/(self.amp_gain/2),
                "TY2": dat[1]['y'],#/(self.amp_gain/2),
                "field_azimuth": ang,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            # self.magnet.shutdown()
            self.magnet.volts = 0
            #self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)