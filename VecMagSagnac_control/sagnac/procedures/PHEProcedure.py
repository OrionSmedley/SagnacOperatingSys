import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.zurich import HF2LI
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from ..custom_instruments import vectorMagnetBase, vectorMagnetX, vectorMagnetY, vectorMagnetZ, vectorMagnetFull
# from scanning import ANC300
from time import sleep, time
import numpy as np

class sagnacPHEProcedure(Procedure):
    """
    Procedure for taking PHE Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    current_frequency = FloatParameter("Applied Sample Voltage frequency", units="kHz", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait time", units = 's', default =1)

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

    DATA_COLUMNS = ["ThetaK","Ratio","X1","Y1","X2","Y2","DeltaThetaK","DeltaThetaK_DualSideband","DeltaX1_C-M", "DeltaY1_C-M", "DeltaX1_C+M", "DeltaY1_C+M","TX1","TY1","TX2","TY2","field_azimuth","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        
        print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        self.magnet = vectorMagnetFull("GPIB::26", "GPIB::25", "GPIB::24") #X,Y,Z in that order

        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        self.lockin.set_vout(1,6,self.applied_voltage/10*np.sqrt(2))

        #subscribe to outputs
        # self.lockin.sub(0)
        # self.lockin.sub(1)
        # self.lockin.sub(2)
        # self.lockin.sub(3)
        # self.lockin.sub(4)
        # self.lockin.sub(5)

        self.stepper = ANC300()
        self.stepper.connect()
        # self.stepper.set_f(self.x_axis, 1000)
        # self.stepper.set_v(self.x_axis, 35)
        # if self.x_enable:
        #     log.info("X enabled")
        #     self.stepper.set_mode(self.x_axis, 'stp')
        # self.stepper.set_f(self.y_axis, 1000)
        # self.stepper.set_v(self.y_axis, 32)
        # if self.y_enable:
        #     log.info("y enabled")
        #     self.stepper.set_mode(self.y_axis, 'stp')
        
    def execute(self):
        if self.x_enable:
            log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
            if self.delta_x >= 0:
                self.stepper.stepu(1, self.delta_x)
            else:
                self.stepper.stepd(1, -self.delta_x)
        if self.y_enable:
            log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
            if self.delta_y >= 0:
                self.stepper.stepu(2, self.delta_y)
            else:
                self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end,
                           self.field_azimuth_step)
        if self.field_azimuth_end not in angles:
            angles = np.append(angles,self.field_azimuth_end)

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

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
        
        log.info("Waiting 5x settling time to equilibrate")
        sleep(self.settling*5)

        num_progress = angles.size
        start_time = time()
        for progress_iterator, ang in enumerate(angles):
            self.emit("progress", 100*progress_iterator/num_progress)
            
            self.magnet.set_field_polar(self.applied_field, ang, self.field_polar)
            log.info(f'Setting B:{self.applied_field} T, phi: {ang}, theta: {self.field_polar}')
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(self.applied_field, ang, self.field_polar, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

            self.lockin.sub(0)
            self.lockin.sub(1)
            self.lockin.sub(2)
            self.lockin.sub(3)
            self.lockin.sub(4)
            self.lockin.sub(5)

            self.lockin.sync() # clears buffer since field has changed
            sleep(self.settling)
            self.lockin.sync()
            dat = self.lockin.poll_and_unpack(0.02, 100, [0,1,2, 3,4,5], ['x','y'], ratio=False)
            log.info("Recording results")
            
            self.lockin.unsubscribe("*")
            
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[2]['y'])/2, #np.arctan(J2J1*np.sign(larger_1)*R1/R2)/2,
                "Ratio": dat[3]['x']/dat[5]['y'], #np.sign(larger_1)*R1/R2,
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[2]['x'],
                "Y2": dat[2]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[2]['y']/2,
                "DeltaThetaK_DualSideband": J2J1*(dat[4]['x'] + dat[5]['x'])/2/dat[2]['y'],
                "DeltaX1_C-M": dat[4]['x'],
                "DeltaY1_C-M": dat[4]['y'],
                "DeltaX1_C+M": dat[5]['x'],
                "DeltaY1_C+M": dat[5]['y'],
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
        log.info("Finished with scans. Shutting down instruments.")
        self.magnet.shutdown()
        while self.magnet.is_ramping():
            sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
                #checking the status for every 22 Gauss change

        Bx, By, Bz = self.magnet.get_field_cartesian()
        if self.magnet.is_holding() and np.isclose(Bx,0,atol=5e-3) and np.isclose(By,0, atol=5e-3) and np.isclose(Bz,0,atol=5e-3):
            log.info("%s" %self.status)
            log.info("Field set to 0T. Finished shutting down")
        else:
            log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")
        # self.stepper.shut_down()