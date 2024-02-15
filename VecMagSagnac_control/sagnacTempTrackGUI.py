import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
from itertools import product
import textwrap
import socket
import numpy as np

from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
from sagnac.procedures import TempTrackingProcedure

class sagnacTempTrackGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['elapsed_time']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacTempTrackGUI, self).__init__(
            procedure_class=TempTrackingProcedure,
            displays=[],
            x_axis='elapsed_time',
            y_axis='ThetaK'
        )
        self.setWindowTitle('PyMeasure Sagnac Temperature Tracking Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacTempTrackGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_TempTrack.ui'))

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = TempTrackingProcedure()
        procedure.wait = self.inputs.wait.value()

        return procedure

    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\junk\\TempTrack'
         
        procedure = self.make_procedure()

        suf = ''
        filename = unique_filename(direc,dated_folder=True,suffix=suf)
        # Queue experiment
        results = Results(procedure,filename)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

    def finished(self, experiment):
        super().finished(experiment)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = sagnacTempTrackGUI()
    window.show()
    sys.exit(app.exec_())
