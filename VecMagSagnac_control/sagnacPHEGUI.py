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
from sagnac.procedures import sagnacPHEProcedure

class sagnacPHEGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['field_azimuth']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacPHEGUI, self).__init__(
            procedure_class=sagnacPHEProcedure,
            displays=[
                'sample_name',
                'applied_field',
                'field_azimuth_start',
                'field_azimuth_end',
                'field_azimuth_step',
                'saturating_field',
                'saturating_field_polar'],
            x_axis='field_azimuth',
            y_axis='TX1'
        )
        self.setWindowTitle('PyMeasure Sagnac PHE Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacPHEGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_PHE.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacPHEProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.x_enable = self.inputs.x_enable.isChecked()
        procedure.y_enable = self.inputs.y_enable.isChecked()

        procedure.applied_voltage = self.inputs.applied_voltage.value()
        procedure.current_frequency = self.inputs.current_frequency.value()*1e3
        procedure.settling = self.inputs.settling.value()
        procedure.wait = self.inputs.wait.value()
        
        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()

        procedure.applied_field = self.inputs.applied_field.value()
        procedure.field_azimuth_start = self.inputs.field_azimuth_start.value()
        procedure.field_azimuth_end = self.inputs.field_azimuth_end.value()
        procedure.field_azimuth_step = self.inputs.field_azimuth_step.value()
        procedure.field_polar = self.inputs.field_polar.value()

        procedure.input_range = self.inputs.input_range.value()
        procedure.imp50 = self.inputs.imp50.isChecked()

        procedure.f_eom = self.inputs.f_eom.value()*1e6

        procedure.first_harm_order = self.inputs.first_harm_order.value()
        procedure.second_harm_order = self.inputs.second_harm_order.value()
        procedure.first_harm_tc = self.inputs.first_harm_tc.value()
        procedure.second_harm_tc = self.inputs.second_harm_tc.value()

        procedure.eom_voltage = self.inputs.eom_voltage.value()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure
    
    def make_motion_sweep(self, steps, delta_x, delta_y):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """
        procedures = []
        for step in steps:
            procedure = self.make_procedure()
            procedure.step = step
            procedure.delta_x = delta_x
            procedure.delta_y = delta_y
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        do_motion_sweep = self.inputs.do_motion_sweep.isChecked()
        if do_motion_sweep:
            steps = range(int(self.inputs.num_step.value()))
            procedures = self.make_motion_sweep(steps, self.inputs.delta_x.value(), self.inputs.delta_y.value())

        else:
            procedures = [self.make_procedure()]
            
        for procedure in procedures:
            if procedure.sample_name == '':
                procedure.sample_name = 'test'

            # create files
            if not do_motion_sweep:
                procedure.step = 0

            pre = procedure.sample_name + \
                '_SagnacPHE_F{field:0.4f}T_V{voltage:0.1f}V_P{polar:0.1f}deg_step{step}_x{delta_x}_y{delta_y}_'.format(
                field=procedure.applied_field,
                voltage=procedure.applied_voltage,
                polar=procedure.field_polar,
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
    window = sagnacPHEGUI()
    window.show()
    sys.exit(app.exec_())
