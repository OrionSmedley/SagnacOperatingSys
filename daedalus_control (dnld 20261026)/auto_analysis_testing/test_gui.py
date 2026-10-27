import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
from pymeasure.experiment import Results, unique_filename

from pymeasure.experiment import Procedure
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import FloatParameter
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.log import console_log
import sys

import numpy as np
from time import sleep
import os

class TestProcedure(Procedure):

    X_start = FloatParameter("X Start Position", units="V", default=-2.)
    X_end = FloatParameter("X End Position", units="V", default=2.)
    X_step = FloatParameter("X Scan Step Size", units="V", default=0.1)
    multiplier = FloatParameter("multiplier", default=1)
    multiplier2 = FloatParameter("multiplier2", default=1)
    delay = FloatParameter("Delay", units="s", default=0.02)

    DATA_COLUMNS = ["X", "dat", "dat2"]

    def startup(self):
        log.info("starting up...")

    def execute(self):
        xs = np.arange(self.X_start,self.X_end,self.X_step)

        nprog = xs.size
        progit = 0
        for x in xs:
            self.emit('progress', int(100*progit/nprog))
            progit += 1
            self.emit("results",{
                'X': x,
                'dat': self.multiplier*np.random.rand(1)[0],
                'dat2': self.multiplier2*100*np.random.rand(1)[0]
            })
            sleep(self.delay)
            if self.should_stop():
                break

    def shutdown(self):
        log.info('shutting down')


class TestGUI(ManagedWindow):

    def __init__(self):
        super(TestGUI, self).__init__(
            procedure_class=TestProcedure,
            x_axis='X',
            y_axis='dat',
            inputs=['X_start','X_end','X_step','multiplier','multiplier2','delay'],
            displays=['X_start', 'X_end', 'multiplier', 'multiplier2', 'delay']
        )
        self.setWindowTitle('Test procedure')

    def start_series(self):
        series_header = '# swept procedure column: X\n'
        series_header += '# swept series parameter: multiplier\n'
        series_header += '# swept series parameter: multiplier2\n'
        series_header += '#\n'
        series_fname='./asweep_file.txt'
        return series_fname, series_header

    def make_procedures(self, mult_start=1, mult_stop=10, mult_step=1):
        multipliers = np.arange(mult_start, mult_stop, mult_step)
        multipliers2 = np.arange(-1*mult_start, -1*mult_stop, -1*mult_step)
        procedures = []
        for mult in multipliers:
            for mult2 in multipliers2:
                print(mult, mult2)
                proc = self.make_procedure()
                proc.multiplier = 10.0**(mult)
                proc.multiplier2 = 10.0**(mult2)
                procedures.append(proc)
        return procedures

    def queue(self):
        direc='.\\'
        procedures = self.make_procedures(1,5,1)
        series_fname, series_header = self.start_series()

        series_file = open(series_fname,'w')
        series_file.write(series_header)

        for proc in procedures:
            filename = unique_filename(direc,'test')
            results = Results(proc, filename)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)
            series_file.write(os.path.split(filename)[-1] + '\n')
        series_file.close()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = TestGUI()
    window.show()
    sys.exit(app.exec_())
