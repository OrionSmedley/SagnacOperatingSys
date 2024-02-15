import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.zurich import HF2LI
from pymeasure.instruments.keithley import Keithley2400
# from ..custom_instruments import daedalusProjField
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class sagnacFieldHysteresisProcedure(Procedure):
    """
    Procedure for taking field-swept Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    field_max = FloatParameter("End Magnetic Field", units="T", default=0.1)
    field_step = FloatParameter("Magnetic Field Step", units="T", default=0.05)
    field_azimuth = FloatParameter("Field Azimuth Angle", units="deg", default=0)
    field_polar = FloatParameter("Field Polar Angle", units="deg", default=0)
    settling = FloatParameter("Settling", units="s", default=0.5)
    reverse = BooleanParameter("Reverse?", default=False)

    apply_current = BooleanParameter("Apply a Current?", default=False)
    current = FloatParameter("Current", units="A", default=1)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)


    input_range = FloatParameter("input range", units="V", default=1)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    output_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["RatioR","RatioY1X2","RatioX1Y2","X1","Y1","X2","Y2","field_strength","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        log.info("Connecting to the magnet")
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        self.lockin.set_range(0, self.input_range)
        self.lockin.set_ac_coupling(0,True)
        self.lockin.set_imp50(0,1)
        self.lockin.set_osc_freq(0,self.f_eom)
        # first harmonic demod
        self.lockin.set_osc_select(0,0)
        self.lockin.set_harmonic(0,1)
        self.lockin.set_phase(0,0)
        self.lockin.set_filter_order(0,self.first_harm_order)
        self.lockin.set_tc(0,self.first_harm_tc)
        self.lockin.set_enable_demod(0,1)
        # second harmonic demod
        self.lockin.set_osc_select(1,0)
        self.lockin.set_harmonic(1,2)
        self.lockin.set_phase(1,0)
        self.lockin.set_filter_order(1,self.second_harm_order)
        self.lockin.set_tc(1,self.second_harm_tc)
        self.lockin.set_enable_demod(1,1)
        # output
        self.lockin.set_outrange(0,1)
        self.lockin.set_vout(0,0,self.output_voltage)
        self.lockin.set_enable_output(0,0,1)
        self.lockin.set_offset(0,0)
        self.lockin.set_sigon(0,1)
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        # self.lockin.sub(2)
        if self.apply_current:
            log.info("Connecting to the Keithley 2400")
            self.source = Keithley2400("GPIB::4")
            #setup keithley
            self.source.apply_current(compliance_voltage=40)
            self.source.compliance_current = 0.025
            self.source.measure_voltage()
            self.source.source_current=0
            self.source.enable_source()
            self.source.voltage_range = 200
            self.source.ramp_to_current(self.current)
            sleep(5)
        
        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True

    def execute(self):
        deg2rad = np.pi/180.
        field_points = np.arange(0,
                                 self.field_max,
                                 self.field_step)
        if self.field_max not in field_points:
            field_points = np.append(field_points,self.field_max)
        field_points = np.append(field_points[::-1],
                                 -1*field_points[1:])
        field_points = np.append(field_points, field_points[::-1][1:])

        if self.reverse:
            field_points = field_points[::-1]
        
        if not self.apply_bias_field:
            self.magnet.set_vector_field(field_points[0], 
                                            phi=self.field_azimuth, 
                                            theta=self.field_polar)
        else:
            self.magnet.set_cart_vector_field(field_points[0]*np.cos(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_x,
                                              field_points[0]*np.sin(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_y,
                                              field_points[0]*np.sin(self.field_polar*deg2rad) + self.bias_field_z)
        sleep(self.settling)

        num_progress = field_points.size
        start_time = time()


        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            if not self.apply_bias_field:
                self.magnet.set_vector_field(field, 
                                             phi=self.field_azimuth, 
                                             theta=self.field_polar)
                log.info(f"Setting magnetic field (polar) to {field},{self.field_azimuth},{self.field_polar}")
            else:
                Bx = field*np.cos(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_x
                By = field*np.sin(self.field_azimuth*deg2rad)*np.cos(self.field_polar*deg2rad) + self.bias_field_y
                Bz = field*np.sin(self.field_polar*deg2rad) + self.bias_field_z
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

            # sleep(self.settling)
            # self.lockin.flush() # clears buffer since field has changed
            self.lockin.sync()
            sleep(self.settling)
            dat = self.lockin.poll_and_unpack(self.settling, 100, [0,1], ['x','y'], ratio=False)
            log.info("Recording results")
            self.emit('results', {
                "RatioR": np.sign(dat[0]['y'])*\
                          np.sqrt(dat[0]['x']**2 + dat[0]['y']**2)/np.sqrt(dat[1]['x']**2 + dat[1]['y']**2),
                "RatioY1X2": dat[0]['y']/dat[1]['x'],
                "RatioX1Y2": dat[0]['x']/dat[1]['y'],
                "X1": dat[0]['x'],
                "Y1": dat[0]['y'],
                "X2": dat[1]['x'],
                "Y2": dat[1]['y'],
                "field_strength": field,
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
            if self.apply_current:
                self.source.ramp_to_current(0)    
            #self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class sagnacDCHysteresisProcedure(Procedure):
    """
    Procedure for taking DC-current-swept Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    current_max = FloatParameter("End DC current", units="mA", default=0.1)
    current_step = FloatParameter("DC Current Step", units="mA", default=0.05)
    reverse = BooleanParameter("Reverses Direction of Current Sweep", default=True)
    hysteresis = BooleanParameter("Hysteretic", default=False)
    settling = FloatParameter("Settling", units="s", default=0.5)

    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    bias_field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
    bias_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    bias_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    output_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["RatioR","RatioY1X2","RatioX1Y2","X1","Y1","X2","Y2","applied_current","elapsed_time"]


    def startup(self):
        log.info("Connecting and configuring the instruments")

        log.info("Connecting to the magnet and moving to saturating field parameters")
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
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

        log.info("Connecting to the Keithley 2400")
        self.source = Keithley2400("GPIB::4")

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        self.lockin.set_range(0, self.input_range)
        self.lockin.set_ac_coupling(0,True)
        self.lockin.set_imp50(0,self.imp50)
        self.lockin.set_osc_freq(0,self.f_eom)
        # first harmonic demod
        self.lockin.set_osc_select(0,0)
        self.lockin.set_harmonic(0,1)
        self.lockin.set_phase(0,0)
        self.lockin.set_filter_order(0,self.first_harm_order)
        self.lockin.set_tc(0,self.first_harm_tc)
        self.lockin.set_enable_demod(0,1)
        # second harmonic demod
        self.lockin.set_osc_select(1,0)
        self.lockin.set_harmonic(1,2)
        self.lockin.set_phase(1,0)
        self.lockin.set_filter_order(1,self.second_harm_order)
        self.lockin.set_tc(1,self.second_harm_tc)
        self.lockin.set_enable_demod(1,1)
        # output
        self.lockin.set_outrange(0,1)
        self.lockin.set_vout(0,0,self.output_voltage)
        self.lockin.set_enable_output(0,0,1)
        self.lockin.set_offset(0,0)
        self.lockin.set_sigon(0,1)
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        
        #setup keithley
        self.source.apply_current(compliance_voltage=40)
        self.source.compliance_current = 0.025
        self.source.measure_voltage()
        self.source.source_current=0
        self.source.enable_source()
        self.source.voltage_range = 200

    def execute(self):
        current_points = np.arange(0,
                                self.current_max,
                                self.current_step)
        if self.current_max not in current_points:
            current_points = np.append(current_points,self.current_max)
        # current_points = current_points[::-1]
        current_points2 = np.append(current_points,
                                    current_points[::-1][1:])
        current_points = np.append(current_points2,-1*current_points[1:])
        if self.hysteresis:
            current_points = np.append(current_points, current_points[::-1][1:])
             
        if self.reverse:
            current_points = current_points[::-1]
        
        self.magnet.set_vector_field(self.saturating_field, 
                                     phi=self.saturating_field_azimuth, 
                                     theta=self.saturating_field_polar)
        self.magnet.volts = 0    
        self.magnet.set_vector_field(0,
                                     phi=self.bias_field_azimuth, 
                                     theta=self.bias_field_polar)
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        self.magnet.set_vector_field(self.bias_field, 
                                     phi=self.bias_field_azimuth, 
                                     theta=self.bias_field_polar)

        num_progress = current_points.size
        start_time = time()

        for progress_iterator, i in enumerate(current_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info(f"Setting DC current to  to {i} A")
            self.source.ramp_to_current(i)
            self.lockin.flush() # clears buffer since field has changed
            sleep(self.settling)
            dat = self.lockin.poll_and_unpack(0.1, 100, [0,1], ['x','y'], ratio=False)
            log.info("Recording results")
            self.emit('results', {
                "RatioR": dat[0]['y']/np.sqrt(dat[1]['x']**2 + dat[1]['y']**2),
                "RatioY1X2": dat[0]['y']/dat[1]['x'],
                "RatioX1Y2": dat[0]['x']/dat[1]['y'],
                "X1": dat[0]['x'],
                "Y1": dat[0]['y'],
                "X2": dat[1]['x'],
                "Y2": dat[1]['y'],
                "applied_current": i,
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
            self.source.source_current = 0
            #self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)