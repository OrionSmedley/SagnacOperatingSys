import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename
from pymeasure.instruments.keithley import Keithley2400, Keithley2182A
from pymeasure.instruments.zurich import HF2LI
from ..instruments.LTC20 import LTC20
# from ..custom_instruments import daedalusProjField
from pymeasure.instruments.keithley import Keithley6221
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from scanning import ANC150
from time import sleep, time
import numpy as np

class sagnacXYScanProcedure(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
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
    num_steps = IntegerParameter("Number of step", default = 1)

    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Averages", default=1)

    # input_range = FloatParameter("input range", units="V", default=1)
    # imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    # f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    # first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    # second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    # first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    # second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    # eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2", "step", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        # log.info(f'Outputing {self.applied_voltage} on output 2 osc 0')
        # self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        # self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)
        
        self.stepper = ANC150("COM3")
        if self.x_enable:
            log.info("X enabled")
            self.stepper.set_mode(self.x_axis, 'stp')
        if self.y_enable:
            log.info("y enabled")
            self.stepper.set_mode(self.y_axis, 'stp')

    def execute(self):
        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        steps = np.arange(0, self.num_steps+1, 1)
        num_progress = steps.size
        start_time = time()

        for progress_iterator, step in enumerate(steps):
            self.emit("progress", 100*progress_iterator/num_progress)

            if self.x_enable:
                log.info(f'Now at step number {step}, moving sample by x:{self.delta_x}')
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

            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y'],
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "TX1": dat[0]['x'],
                "TY1": dat[0]['y'],
                "TX2": dat[1]['x'],
                "TY2": dat[1]['y'],
                "step": step,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        self.stepper.shut_down()