#############################################################################################################################

from PyQt5 import QtWidgets, QtGui

# Map all attributes from QtWidgets to QtGui without checking if they exist in QtGui
for attr in dir(QtWidgets):
    setattr(QtGui, attr, getattr(QtWidgets, attr))

#############################################################################################################################
import pyvisa

# Simulate the `visa` module as an alias for `pyvisa`
import sys

# Create a fake 'visa' module, which is essentially an alias for pyvisa
sys.modules['visa'] = pyvisa

# Optionally, map all attributes from pyvisa to visa (this is technically unnecessary because the alias works)
for attr in dir(pyvisa):
    setattr(sys.modules['visa'], attr, getattr(pyvisa, attr))

#############################################################################################################################

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

#############################################################################################################################

from PyQt5 import QtWidgets, QtGui

# Map all attributes from QtWidgets to QtGui without checking if they exist in QtGui
for attr in dir(QtWidgets):
    setattr(QtGui, attr, getattr(QtWidgets, attr))

#############################################################################################################################
import pyvisa

# Simulate the `visa` module as an alias for `pyvisa`
import sys

# Create a fake 'visa' module, which is essentially an alias for pyvisa
sys.modules['visa'] = pyvisa

# Optionally, map all attributes from pyvisa to visa (this is technically unnecessary because the alias works)
for attr in dir(pyvisa):
    setattr(sys.modules['visa'], attr, getattr(pyvisa, attr))

#############################################################################################################################

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
from sagnac.procedures import sagnacOpticsXportProcedure_vm_PhiSweep_usbMagCom
from PyQt5 import QtWidgets
class sagnacHeterodynePhiSweepGUI_usb(ManagedWindow):

    SWEEP_PARAM_NAMES = ['sweep_phi', 'sweep_phi_polar']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacHeterodynePhiSweepGUI_usb, self).__init__(
            procedure_class=sagnacOpticsXportProcedure_vm_PhiSweep_usbMagCom,
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
            y_axis='ThetaK',
            enable_file_input = False
        )
        self.setWindowTitle('PyMeasure Sagnac Heterodyne Hysteresis Scan for Phi Sweep')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacHeterodynePhiSweepGUI_usb, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_HeterodynePhiSweep.ui'))
        self.inputs.save_dir.setText("test")
    
    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacOpticsXportProcedure_vm_PhiSweep_usbMagCom()
        procedure.sample_name = self.inputs.sample_name.text()

        # procedure.current_amplitude = self.inputs.current_amplitude.value()/1e3
        procedure.applied_current = self.inputs.applied_current.value()
        # procedure.current_frequency = self.inputs.current_frequency.value()*1e3
        # procedure.current_offset = self.inputs.current_offset.value()/1e3
        procedure.applied_voltage = self.inputs.applied_voltage.value()
        # procedure.amp_gain = self.inputs.amp_gain.value()
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
        procedure.r_threshold = self.inputs.r_threshold.value()

        # procedure.bias_field_x = self.inputs.bias_field_x.value()
        # procedure.bias_field_y = self.inputs.bias_field_y.value()
        # procedure.bias_field_z = self.inputs.bias_field_z.value()

        # procedure.input_range = self.inputs.input_range.value()
        # procedure.imp50 = self.inputs.imp50.isChecked()

        procedure.f_eom = self.inputs.f_eom.value()*1e6

        # procedure.first_harm_order = self.inputs.first_harm_order.value()
        # procedure.second_harm_order = self.inputs.second_harm_order.value()
        # procedure.first_harm_tc = self.inputs.first_harm_tc.value()
        # procedure.second_harm_tc = self.inputs.second_harm_tc.value()

        # procedure.eom_voltage = self.inputs.eom_voltage.value()
        procedure.voltage_sweep = self.inputs.do_voltage_sweep.isChecked()
        procedure.voltage_start = self.inputs.voltage_start.value()
        procedure.voltage_stop = self.inputs.voltage_stop.value()
        procedure.voltage_step = self.inputs.voltage_step.value()
        procedure.voltage_scale_main = self.inputs.voltage_scale_main.isChecked()
        procedure.voltage_scale_sub = self.inputs.voltage_scale_sub.isChecked()

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure
    
    def make_field_sweep(self, sweep_phis, sweep_phi_polar, v):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """
        procedures = []
        for phi in sweep_phis:
            procedure = self.make_procedure()
            procedure.applied_voltage = v
            procedure.sweep_phi = phi
            procedure.sweep_phi_polar = sweep_phi_polar
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures
    
    def single_voltage_sweep(self, v):
        """
        Makes one voltage sweep
        """
        # procedures = []
        procedure = self.make_procedure()
        procedure.applied_voltage = v
        procedure.first = False
        procedure.last = False
        # procedures.append(procedure)
        return [procedure]

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

        print("check procedures: (len), procedures ", len(procedures), procedures)
        return procedures

    def queue(self):
        direc = 'C:\\Users\\luogroup\\Documents\\Sagnac Data\\' + self.inputs.save_dir.text()
        # procedure = self.make_procedure()
        do_voltage_sweep = self.inputs.do_voltage_sweep.isChecked()
        procedures = []
        if do_voltage_sweep:
            if (self.inputs.voltage_start.value() > self.inputs.voltage_stop.value()):
                voltages = np.arange(self.inputs.voltage_start.value(), 
                                self.inputs.voltage_stop.value(), 
                                -1 * self.inputs.voltage_step.value())
            else: 
                voltages = np.arange(self.inputs.voltage_start.value(), 
                                self.inputs.voltage_stop.value(), 
                                self.inputs.voltage_step.value())
            if self.inputs.voltage_stop.value() not in voltages:
                voltages = np.append(voltages,self.inputs.voltage_stop.value())
            # procedures += self.make_voltage_sweep(voltages)
            # print("check voltage list: ", voltages)
            for v in voltages:
                for i in range(int(self.inputs.num_repeat.value())):
                    # print("check combo: ", v, i)
                    # test_list += self.single_voltage_sweep(v)
                    procedures += self.single_voltage_sweep(v)
                    # if do_motion_sweep:
                    #     steps = range(int(self.inputs.num_step.value()))
                    #     procedures += self.make_motion_sweep(steps, self.inputs.delta_x.value(), self.inputs.delta_y.value())
                    
                    
                    # elif do_fourQuadrant:
                    #     procedures += self.make_4quadrant_sweep()
                    # else:
                    #     procedures += [self.make_procedure()]
                
            # print("check procedure: ", test_list)
        else: 
            for i in range( int(self.inputs.num_repeat.value())):
                    procedures += [self.make_procedure()]
        print("check procedures: ", procedures)
        for procedure in procedures: 
            if procedure.sample_name == '':
                procedure.sample_name = 'test'

            # create files
            pre = procedure.sample_name + \
                '_SagnacHeterodyne_V{voltage:0.4f}V_A{polar:0.1f}_step{step}_B{applied_field}B_'.format(
                voltage=procedure.applied_voltage,
                polar=procedure.sweep_phi_polar,
                step = procedure.sweep_phi_step, 
                applied_field = procedure.sweep_phi_field
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
    app = QtWidgets.QApplication(sys.argv)
    window = sagnacHeterodynePhiSweepGUI_usb()
    window.show()
    sys.exit(app.exec_())
