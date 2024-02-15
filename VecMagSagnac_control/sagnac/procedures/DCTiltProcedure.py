import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.zurich import HF2LI
from ..custom_instruments import vectorMagnetBase, vectorMagnetX, vectorMagnetY, vectorMagnetZ, vectorMagnetFull
from ..instruments.LTC20 import LTC20
# from ..custom_instruments import daedalusProjField
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class sagnacDCTiltProcedure(Procedure):

    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup using vector magnet
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    current = FloatParameter("Applied Sample current", units="V", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre measurement wait time", units="s", default=0.5)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    pm_field = BooleanParameter("Plus and Minus Field?", default=True)
    sweep_field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
    sweep_field_step = FloatParameter("Bias Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

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

    DATA_COLUMNS = ["ThetaK","Ratio","X1","Y1","X2","Y2","sweep_field","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        log.info("Connecting to the magnet")
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)

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
        self.lockin.sub(3)
        self.lockin.sub(5)
        # self.lockin.sub(5)
        log.info("Connecting to the Keithley 2400")
        self.source = Keithley2400("GPIB::4")
        #setup keithley
        self.source.apply_current(compliance_voltage=10)
        self.source.compliance_current = 0.025
        self.source.measure_voltage()
        self.source.source_current=0
        self.source.enable_source()
        self.source.voltage_range = 200
        self.source.ramp_to_current(self.current)
        sleep(self.settling*5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True

    def execute(self):
        J2J1 = 0.543
        # J1J0 = 1.837
        deg2rad = np.pi/180.
        field_points = np.arange(0,
                                 self.sweep_field,
                                 self.sweep_field_step)
        if self.sweep_field not in field_points:
            field_points = np.append(field_points,self.sweep_field)
        
        field_points = field_points[::-1]

        if self.pm_field:
            field_points = np.append(field_points,
                                    -1*field_points[::-1][1:])
        if self.hysteresis:                        
            field_points = np.append(field_points, field_points[::-1][1:])

        if self.reverse:
            field_points = field_points[::-1]
        
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
            nom_x, _, _ = self.magnet.angle_calibration(self.saturating_field_polar, self.saturating_field_azimuth) #temporary fix for bad x axis
            att = 1
            while not np.isclose(self.magnet.motion_inst.x.position, nom_x, atol=1e-3): #temporary fix for bad x axis
                self.magnet.motion_inst.x.enable()
                self.magnet.motion_inst.x.position = nom_x
                sleep(0.1)
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                att = att + 1
                log.info(f"attempt number {att}")
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
        
        if not self.apply_bias_field:
            # ensure we have gotten to the phi we want
            while not np.isclose(self.magnet.phi, self.sweep_field_azimuth, atol=1e-3):
                log.info(f"setting magnet azimuthal orientation to {self.sweep_field_azimuth} deg")
                self.magnet.phi = self.sweep_field_azimuth
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
            # NOTE: in the future will probably want to check that we have actually reached
            # the theta value we set it to.
            log.info(f"setting magnet polar orientation to {self.sweep_field_polar} degrees")
            self.magnet.theta = self.sweep_field_polar
            nom_x, _, _ = self.magnet.angle_calibration(self.sweep_field_polar, self.sweep_field_azimuth) #temporary fix for bad x axis
            att = 1
            while not np.isclose(self.magnet.motion_inst.x.position, nom_x, atol=1e-3): #temporary fix for bad x axis
                self.magnet.motion_inst.x.enable()
                self.magnet.motion_inst.x.position = nom_x
                sleep(0.1)
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                att = att + 1
                log.info(f"attempt number {att}")
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            log.info("Setting Sweep Field")
            self.magnet.field = field_points[0]
            log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")

        else:
            self.magnet.set_cart_vector_field(field_points[0]*np.cos(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_x,
                                              field_points[0]*np.sin(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_y,
                                              field_points[0]*np.sin(self.sweep_field_polar*deg2rad) + self.bias_field_z)
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)

        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        log.info("Waiting a while to equilibrate")
        sleep(self.wait)

        num_progress = field_points.size
        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            if not self.apply_bias_field:
                self.magnet.field = field
                log.info(f"Setting Magnetic Field to {field:.5f} T")
            else:
                Bx = field*np.cos(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_x
                By = field*np.sin(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_y
                Bz = field*np.sin(self.sweep_field_polar*deg2rad) + self.bias_field_z
                self.magnet.set_cart_vector_field(Bx,By,Bz)
                log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                log.info(f"This corresponds to location {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")

            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            
            sleep(self.settling)
            self.lockin.sync() # clears buffer since field has changed
            dat = self.lockin.poll_and_unpack(0.02, 100, [3,5], ['x','y'], ratio=False)
            log.info("Recording results")
            # R1 = np.sqrt(dat[0]['x']**2 + dat[0]['y']**2)
            # R2 = np.sqrt(dat[1]['x']**2 + dat[1]['y']**2)
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2,
                "Ratio": dat[3]['x']/dat[5]['y'],
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "sweep_field": field,
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
            self.source.ramp_to_current(0)
            #self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)


class sagnacDCTiltCurrentProcedure(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')
    field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
    field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Wait Time", units="s", default=0.5)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    current = FloatParameter("Applied Sample Current Max", units="A", default=0.1)
    current_step = FloatParameter("Applied Sample Current Max", units="A", default=0.1)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

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

    DATA_COLUMNS = ["ThetaK","Ratio","X1","Y1","X2","Y2","current","Bx", "By", "Bz", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        
        print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        self.magnet = vectorMagnetFull("GPIB::23", "GPIB::22", "GPIB::21") #X,Y,Z in that order
      
        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)

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
        self.lockin.sub(3)
        self.lockin.sub(5)
        # self.lockin.sub(5)
        log.info("Connecting to the Keithley 2400")
        self.source = Keithley2400("GPIB::30")
        #setup keithley
        # self.source.apply_current(compliance_voltage=40)
        # self.source.compliance_current = 0.025
        # self.source.measure_voltage()
        # self.source.source_current=0
        # self.source.enable_source()
        # self.source.voltage_range = 200
        sleep(self.settling*5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True

    def execute(self):
        J2J1 = 0.543
        # J1J0 = 1.837
        deg2rad = np.pi/180.
        current_points = np.arange(0,
                                 self.current,
                                 self.current_step)
        if self.current not in current_points:
            current_points = np.append(current_points,self.current)
        
        current_points = current_points[::-1]
        current_points = np.append(current_points, -1*current_points[::-1][1:])

        if self.reverse:
            current_points = current_points[::-1]
    
        if self.hysteresis:                        
            current_points = np.append(current_points, current_points[::-1][1:])

       
        
        if self.saturate:

            self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
            log.info("Setting saturation field")
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break


            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

        #Checking magnet's status to ensure that it successfully reaches the
        #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
            # # ensure we have gotten to the phi we want
            # while not np.isclose(self.magnet.phi, self.saturating_field_azimuth, atol=1e-3):
            #     log.info(f"setting magnet azimuthal orientation to {self.saturating_field_azimuth} deg")
            #     self.magnet.phi = self.saturating_field_azimuth
            #     while self.magnet.in_motion: # wait for all motion to finish
            #         sleep(0.1)
            #     for err in self.magnet.errors:
            #         log.warning('%s'%err)
            # # NOTE: in the future will probably want to check that we have actually reached
            # # the theta value we set it to.
            # log.info(f"setting magnet polar orientation to {self.saturating_field_polar} degrees")
            # self.magnet.theta = self.saturating_field_polar
            # nom_x, _, _ = self.magnet.angle_calibration(self.saturating_field_polar, self.saturating_field_azimuth) #temporary fix for bad x axis
            # att = 1
            # while not np.isclose(self.magnet.motion_inst.x.position, nom_x, atol=1e-3): #temporary fix for bad x axis
            #     self.magnet.motion_inst.x.enable()
            #     self.magnet.motion_inst.x.position = nom_x
            #     sleep(0.1)
            #     while self.magnet.in_motion: # wait for all motion to finish
            #         sleep(0.1)
            #     for err in self.magnet.errors:
            #         log.warning('%s'%err)
            #     att = att + 1
            #     log.info(f"attempt number {att}")
            # while self.magnet.in_motion: # wait for all motion to finish
            #     sleep(0.1)
            # for err in self.magnet.errors:
            #     log.warning('%s'%err)
            # log.info("Setting the Saturating Field")
            # self.magnet.set_vector_field(self.saturating_field,
            #                              phi=self.saturating_field_azimuth, 
            #                              theta=self.saturating_field_polar)
            # log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")
            # sleep(self.settling)

            # self.magnet.volts = 0
        
        if not self.apply_bias_field:
            self.magnet.set_field_polar(self.field, self.field_azimuth, self.field_polar)  #saturate the field 
            log.info("Setting field")
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break


            while not self.magnet.check_field_polar(self.field, self.field_azimuth, self.field_polar, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

        #Checking magnet's status to ensure that it successfully reaches the
        #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

        #     # ensure we have gotten to the phi we want
        #     while not np.isclose(self.magnet.phi, self.field_azimuth, atol=1e-3):
        #         log.info(f"setting magnet azimuthal orientation to {self.field_azimuth} deg")
        #         self.magnet.phi = self.field_azimuth
        #         while self.magnet.in_motion: # wait for all motion to finish
        #             sleep(0.1)
        #         for err in self.magnet.errors:
        #             log.warning('%s'%err)
        #     # NOTE: in the future will probably want to check that we have actually reached
        #     # the theta value we set it to.
        #     log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        #     self.magnet.theta = self.field_polar
        #     nom_x, _, _ = self.magnet.angle_calibration(self.field_polar, self.field_azimuth) #temporary fix for bad x axis
        #     att = 1
        #     while not np.isclose(self.magnet.motion_inst.x.position, nom_x, atol=1e-3): #temporary fix for bad x axis
        #         self.magnet.motion_inst.x.enable()
        #         self.magnet.motion_inst.x.position = nom_x
        #         sleep(0.1)
        #         while self.magnet.in_motion: # wait for all motion to finish
        #             sleep(0.1)
        #         for err in self.magnet.errors:
        #             log.warning('%s'%err)
        #         att = att + 1
        #         log.info(f"attempt number {att}")
        #     while self.magnet.in_motion: # wait for all motion to finish
        #         sleep(0.1)
        #     for err in self.magnet.errors:
        #         log.warning('%s'%err)
        #     log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")

        # else:
        #     self.magnet.set_cart_vector_field(self.field*np.cos(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_x,
        #                                       self.field*np.sin(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_y,
        #                                       self.field*np.sin(self.field_polar*deg2rad) + self.bias_field_z)
        #     while self.magnet.in_motion: # wait for all motion to finish
        #         sleep(0.1)
        #     for err in self.magnet.errors:
        #         log.warning('%s'%err)

        # while self.magnet.in_motion: # wait for all motion to finish
        #     sleep(0.1)
        # for err in self.magnet.errors:
        #     log.warning('%s'%err)
        # if not self.apply_bias_field:
        #     self.magnet.field = self.field
        #     log.info(f"Setting Magnetic Field to {self.field:.5f} T")
        else:
            Bx = self.field*np.cos(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_x
            By = self.field*np.sin(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_y
            Bz = self.field*np.sin(self.field_polar*deg2rad) + self.bias_field_z

            self.magnet.set_field_cartesian(Bx, By, Bz)
            log.info("Setting bias field")
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break


            while not self.magnet.check_field_cartesian(Bx, By, Bz, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

        #Checking magnet's status to ensure that it successfully reaches the
        #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
            # self.magnet.set_cart_vector_field(Bx,By,Bz)
            # log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
            # while self.magnet.in_motion: # wait for all motion to finish
            #     sleep(0.1)
            # for err in self.magnet.errors:
            #     log.warning('%s'%err)
            # log.info(f"This corresponds to location {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")
        
        log.info("Waiting for the wait time")
        sleep(self.wait)


        log.info("Waiting a while to equilibrate")
        self.source.ramp_to_current(current_points[0])
        sleep(self.settling*10)

        num_progress = current_points.size
        start_time = time()

        for progress_iterator, i in enumerate(current_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info(f"Setting DC current to {i:.4f} A")
            self.source.ramp_to_current(i)
            
            self.lockin.sync() # clears buffer since field has changed
            sleep(self.settling)
            dat = self.lockin.poll_and_unpack(0.02, 100, [3,5], ['x','y'], ratio=False)

            log.info("Recording results")
            rec_Bx,rec_By,rec_Bz = self.magnet.get_field_cartesian()
            sleep(0.5)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break
           
            # R1 = np.sqrt(dat[0]['x']**2 + dat[0]['y']**2)
            # R2 = np.sqrt(dat[1]['x']**2 + dat[1]['y']**2)
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2,
                "Ratio": dat[3]['x']/dat[5]['y'],
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "current": i,
                "Bx":rec_Bx,
                "By":rec_By, 
                "Bz":rec_Bz,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            # self.magnet.shutdown()
            # self.magnet.volts = 0
            self.source.ramp_to_current(0)
            #self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)