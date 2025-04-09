import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.experiment import Procedure
from pymeasure.experiment import Parameter, FloatParameter, IntegerParameter
import numpy as np
from time import sleep
try:
    from pymeasure.instruments.agilent import Agilent8722ES
except ImportError as e:
    log.warning("Could not load instruments for the procedure class")
    #log.exception(e)

class VNAProcedure(Procedure):

    sample = Parameter('Sample')
    frequency_start = FloatParameter('Initial RF frequency', units='GHz', default=5.0)
    frequency_end = FloatParameter('Final RF frequency', units='GHz', default=30.0)

    frequency_points = IntegerParameter('Number of Frequency Points sampled', default = 21)

    num_averages = IntegerParameter("Number of Averages", default=16)

    S_param = IntegerParameter("S Paramater", default = 11)

    start_time = Parameter('Start time')

    DATA_COLUMNS = ['frequency', 'ReS', 'ImS', 'magS','Gamma','Z'] # TODO: do we want more S params?

    def startup(self):

        log.info("Initializing instruments")
        self.vna = Agilent8722ES('GPIB::16') # TODO: GPIB address
        self.vna.start_frequency = self.frequency_start*1e9
        self.vna.stop_frequency = self.frequency_end*1e9
        self.vna.scan_points = self.frequency_points
        if self.S_param == 11:
            self.vna.parameter="S11"
        elif self.S_param == 21:
            self.vna.parameter="S21"
        else:
            raise ValueError("Please Enter a valid S parameter")

        log.info('finished Initializing')

        sleep(0.1)
    def execute(self):
        log.info('beginning the scan')
        self.vna.scan(self.num_averages, blocking=True, timeout=1000)

        log.info('Reading the data')

        VNA_data_re, VNA_data_im = self.vna.data
        fs = self.vna.frequencies

        for re, im, f in zip(VNA_data_re, VNA_data_im, fs):
            # TODO: Figure out of averaging should be digital??
            magS = np.sqrt(re**2 + im**2)
            Gamma = 10**(-magS/20)
            Z = 50*(1+Gamma)/(1-Gamma)
            self.emit('results', {
                'frequency': f/1e9,
                'ReS': re,
                'ImS': im,
                'magS': magS,
                'Gamma': Gamma,
                'Z': Z
                })

    def shutdown(self):
        log.info("Experiment finished")

        sleep(0.5)
