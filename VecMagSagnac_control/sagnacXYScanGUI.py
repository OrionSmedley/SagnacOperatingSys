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
from sagnac.procedures import sagnacXYScanProcedure

class sagnacXYScanGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['sweep_field', 'sweep_field_azimuth']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacXYScanGUI, self).__init__(
            procedure_class=sagnacXYScanProcedure,
            displays=['sample_name'],
            x_axis='step',
            y_axis='ThetaK'
        )
        self.setWindowTitle('PyMeasure Sagnac XY Motion Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacXYScanGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_XYScan.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacXYScanProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.x_enable = self.inputs.x_enable.isChecked()
        procedure.y_enable = self.inputs.y_enable.isChecked()
        procedure.delta_x = self.inputs.delta_x.value()
        procedure.delta_y = self.inputs.delta_y.value()
        procedure.num_steps = self.inputs.num_steps.value()

        procedure.settling = self.inputs.settling.value()
        procedure.wait = self.inputs.wait.value()

        
        # procedure.input_range = self.inputs.input_range.value()
        # procedure.imp50 = self.inputs.imp50.isChecked()
        # procedure.f_eom = self.inputs.f_eom.value()*1e6

        # procedure.first_harm_order = self.inputs.first_harm_order.value()
        # procedure.second_harm_order = self.inputs.second_harm_order.value()
        # procedure.first_harm_tc = self.inputs.first_harm_tc.value()
        # procedure.second_harm_tc = self.inputs.second_harm_tc.value()

        # procedure.eom_voltage = self.inputs.eom_voltage.value()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        procedures = [self.make_procedure()]
            
        for procedure in procedures:
            if procedure.sample_name == '':
                procedure.sample_name = 'test'

            pre = procedure.sample_name + \
                'XYScan_step{step}_x{delta_x}_y{delta_y}_'.format(
                step = procedure.step,
                delta_x = procedure.delta_x,
                delta_y = procedure.delta_y
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
    window = sagnacXYScanGUI()
    window.show()
    sys.exit(app.exec_())
