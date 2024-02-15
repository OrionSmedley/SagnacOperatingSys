import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.zurich import HF2LI
# from pymeasure.instruments.lakeshore import LakeShore331
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from time import sleep, time
import numpy as np

class TempTrackingProcedure(Procedure):

    """
    Procedure for tracking the temperature with the Sagnac setup
    """

    wait = FloatParameter("Wait time between data recording", units="s", default=0.5)
    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y2","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        # log.info("Connecting to the Lakeshore")
        # self.ls = LakeShore331("GPIB::12") 

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        #subscribe to outputs
        self.lockin.sub(3)
        self.lockin.sub(5)

    def execute(self):
        J2J1 = 0.543
        start_time = time()

        while not self.should_stop():
            dat = self.lockin.poll_and_unpack(self.wait, 100, [3,5], ['x','y'], ratio=False)
            self.emit('results', {
                # "Temperature": self.ls.temperature_A,
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2,
                "X1": dat[3]['x'],
                "Y2": dat[5]['y'],
                "elapsed_time": time()-start_time
                })
            sleep(self.wait)

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished recording temperature")
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
