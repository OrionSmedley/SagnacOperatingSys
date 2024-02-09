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
from sagnac.procedures import AMRKeithleyProcedure

class sagnacAMRKeithleyGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['field_azimuth']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacAMRKeithleyGUI, self).__init__(
            procedure_class=AMRKeithleyProcedure,
            displays=[
                'sample_name',
                'applied_field',
                'field_azimuth_start',
                'field_azimuth_end',
                'field_azimuth_step'],
            x_axis='field_azimuth',
            y_axis='R'
        )
        self.setWindowTitle('PyMeasure Sagnac AMR Keithley Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacAMRKeithleyGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_AMR_Keithley.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = AMRKeithleyProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.applied_field = self.inputs.applied_field.value()
        procedure.field_azimuth_start = self.inputs.field_azimuth_start.value()
        procedure.field_azimuth_end = self.inputs.field_azimuth_end.value()
        procedure.field_azimuth_step = self.inputs.field_azimuth_step.value()
        procedure.field_polar = self.inputs.field_polar.value()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure
    
    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        procedure = self.make_procedure()
        if procedure.sample_name == '':
            procedure.sample_name = 'test'

        # create files
        pre = procedure.sample_name + \
            '_SagnacPHE_F{field:0.4f}T_P{polar:0.1f}deg_'.format(
            field=procedure.applied_field,
            polar=procedure.field_polar,
        )
        suf = ''
        filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                    prefix=pre)
        # Queue experiment
        results = Results(procedure,filename)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

    def finished(self, experiment):
        super().finished(experiment)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = sagnacAMRKeithleyGUI()
    window.show()
    sys.exit(app.exec_())
