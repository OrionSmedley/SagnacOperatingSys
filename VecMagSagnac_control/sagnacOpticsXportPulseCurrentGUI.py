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
from sagnac.procedures import sagnacOpticsXportPulseCurrentProcedure_vm

class sagnacOpticsXportPulseCurrentGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['sweep_field', 'sweep_field_azimuth']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacOpticsXportPulseCurrentGUI, self).__init__(
            procedure_class=sagnacOpticsXportPulseCurrentProcedure_vm,
            displays=[
                'sample_name',
                'current_frequency',
                'amp_gain',
                'sweep_current_0',
                'sweep_current_1',
                'sweep_current_2',
                'sweep_current_3',
                'sweep_current_num_1',
                'sweep_current_num_2',
                'pulsewidth',
                'sweep_field',
                'sweep_field_azimuth',
                'sweep_field_polar',
                'saturating_field',
                'saturating_field_azimuth',
                'saturating_field_polar',
                'bias_field_x',
                'bias_field_y',
                'bias_field_z'],
            x_axis='sweep_current',
            y_axis='ThetaK'
        )
        self.setWindowTitle('PyMeasure Sagnac Vector Magnet Optics Xport Combo Pulse Current Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacOpticsXportPulseCurrentGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_OpticsXportPulseCurrent.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacOpticsXportPulseCurrentProcedure_vm()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.x_enable = self.inputs.x_enable.isChecked()
        procedure.y_enable = self.inputs.y_enable.isChecked()

        # procedure.current_amplitude = self.inputs.current_amplitude.value()/1e3
        procedure.applied_voltage = self.inputs.applied_voltage.value()
        procedure.current_frequency = self.inputs.current_frequency.value()
        # procedure.current_offset = self.inputs.current_offset.value()/1e3
        procedure.amp_gain = self.inputs.amp_gain.value()
        procedure.settling = self.inputs.settling.value()
        procedure.wait = self.inputs.wait.value()

        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()

        procedure.sweep_current_0 = self.inputs.sweep_current_0.value()
        procedure.sweep_current_1 = self.inputs.sweep_current_1.value()
        procedure.sweep_current_2 = self.inputs.sweep_current_2.value()
        procedure.sweep_current_3 = self.inputs.sweep_current_3.value()
        procedure.sweep_current_num_1 = self.inputs.sweep_current_num_1.value()
        procedure.sweep_current_num_2 = self.inputs.sweep_current_num_2.value()
        procedure.pulsewidth = self.inputs.pulsewidth.value()*1e-6

        procedure.sweep_field = self.inputs.sweep_field.value()
        procedure.sweep_field_azimuth = self.inputs.sweep_field_azimuth.value()
        procedure.sweep_field_polar = self.inputs.sweep_field_polar.value()

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
    
    def make_voltage_sweep(self, voltages):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """
        procedures = []
        for v in voltages:
            procedure = self.make_procedure()
            procedure.applied_voltage = v
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

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
        # do_sweep = self.inputs.do_voltage_sweep.isChecked()
        # if do_sweep:
        #     voltages = np.arange(self.inputs.voltage_min.value(), 
        #                          self.inputs.voltage_max.value(), 
        #                          self.inputs.voltage_step.value())
        #     if self.inputs.voltage_max.value() not in voltages:
        #         voltages = np.append(voltages,self.inputs.voltage_max.value())
        #     procedures = self.make_voltage_sweep(voltages)

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
                '_SagnacHeterodyne_V{voltage:0.4f}V_A{azimuth:0.1f}_step{step}_x{delta_x}_y{delta_y}_'.format(
                voltage=procedure.applied_voltage,
                azimuth=procedure.sweep_field_azimuth,
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
    window = sagnacOpticsXportPulseCurrentGUI()
    window.show()
    sys.exit(app.exec_())
