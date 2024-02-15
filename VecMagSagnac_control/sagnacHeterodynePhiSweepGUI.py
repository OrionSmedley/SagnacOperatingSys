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
from sagnac.procedures import sagnacHeterodyneProcedure_vm_PhiSweep
class sagnacHeterodynePhiSweepGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['sweep_phi', 'sweep_phi_polar']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacHeterodynePhiSweepGUI, self).__init__(
            procedure_class=sagnacHeterodyneProcedure_vm_PhiSweep,
            displays=[
                'sample_name',
                'amp_gain',
                'sweep_phi_field',
                'sweep_phi_step',
                'saturating_field',
                'saturating_field_polar',
                'bias_field_x',
                'bias_field_y',
                'bias_field_z'],
            x_axis='sweep_phi',
            y_axis='ThetaK'
        )
        self.setWindowTitle('PyMeasure Sagnac Heterodyne Hysteresis Scan for Phi Sweep')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacHeterodynePhiSweepGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_HeterodynePhiSweep.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacHeterodyneProcedure_vm_PhiSweep()
        procedure.sample_name = self.inputs.sample_name.text()

        # procedure.current_amplitude = self.inputs.current_amplitude.value()/1e3
        procedure.applied_current = self.inputs.applied_current.value()
        # procedure.current_frequency = self.inputs.current_frequency.value()*1e3
        # procedure.current_offset = self.inputs.current_offset.value()/1e3
        procedure.amp_gain = self.inputs.amp_gain.value()
        procedure.settling = self.inputs.settling.value()
        procedure.wait = self.inputs.wait.value()

        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()

        procedure.hysteresis = self.inputs.hysteresis.isChecked()
        procedure.reverse = self.inputs.reverse.isChecked()
        procedure.sweep_phi_start = self.inputs.sweep_phi_start.value()
        procedure.sweep_phi_end = self.inputs.sweep_phi_end.value()
        procedure.sweep_phi_step = self.inputs.sweep_phi_step.value()
        procedure.sweep_phi_field = self.inputs.sweep_phi_field.value()
        procedure.sweep_phi_polar = self.inputs.sweep_phi_polar.value()

        procedure.bias_field_x = self.inputs.bias_field_x.value()
        procedure.bias_field_y = self.inputs.bias_field_y.value()
        procedure.bias_field_z = self.inputs.bias_field_z.value()

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
    
    def make_field_sweep(self, sweep_phis, sweep_phi_polar):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """
        procedures = []
        for phi in sweep_phis:
            procedure = self.make_procedure()
            procedure.sweep_phi = phi
            procedure.sweep_phi_polar = sweep_phi_polar
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        procedure = self.make_procedure()
        if procedure.sample_name == '':
            procedure.sample_name = 'test'

        # create files
        pre = procedure.sample_name + \
            '_SagnacHeterodyne_V{current:0.4f}V_A{polar:0.1f}_'.format(
            current=procedure.applied_current,
            polar=procedure.sweep_phi_polar,
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
    window = sagnacHeterodynePhiSweepGUI()
    window.show()
    sys.exit(app.exec_())
