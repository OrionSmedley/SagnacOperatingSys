import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
from itertools import product
import time
import textwrap
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
from daedalus.procedures import VNAProcedure
from pymeasure.instruments.agilent import Agilent8722ES

import numpy as np

class VNAGUI(ManagedWindow):

    def __init__(self):
        super().__init__(
            procedure_class=VNAProcedure,
            x_axis='frequency',
            y_axis='ReS',
            displays=['sample','frequency_start', 'frequency_end', 'num_averages']
        )
        self.setWindowTitle('PyMeasure VNA Measurement')

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus STFMR measurements
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs\\daedalus_gui_VNA.ui'))

    def make_procedure(self):
        procedure = VNAProcedure()

        procedure.sample = self.inputs.sample_name.text()
        procedure.frequency_points = Agilent8722ES.SCAN_POINT_VALUES[self.inputs.frequency_points.currentIndex()]

        procedure.num_averages = self.inputs.num_averages.value()

        procedure.frequency_start = self.inputs.frequency_start.value()
        procedure.frequency_end = self.inputs.frequency_stop.value() # VNA behaves like linspace, image plotting assumes arange
        procedure.start_time = time.strftime("%Y-%m-%d %I:%M%p").lower()

        Sps = [11, 21]
        procedure.S_param = Sps[self.inputs.S_param.currentIndex()]

        return procedure

    def queue(self):
        sname = self.inputs.sample_name.text()
        save_dir = self.inputs.save_dir.text()
        pre = (sname + '_') if sname else ''
        suf = '_VNA'
        filename = unique_filename(save_dir,dated_folder=True,suffix=suf,prefix=pre)

        procedure = self.make_procedure()
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = VNAGUI()
    window.show()
    sys.exit(app.exec_())
