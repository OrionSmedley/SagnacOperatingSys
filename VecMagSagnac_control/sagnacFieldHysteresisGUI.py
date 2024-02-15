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
from sagnac.procedures import sagnacFieldHysteresisProcedure

class sagnacHysteresisGUI(ManagedWindow):

    def __init__(self):
        super(sagnacHysteresisGUI, self).__init__(
            procedure_class=sagnacFieldHysteresisProcedure,
            displays=[
                'sample_name',
                'current',
                'field_max',
                'field_step',
                'field_azimuth',
                'field_polar'],
            x_axis='field_strength',
            y_axis='RatioR'
        )
        self.setWindowTitle('PyMeasure Sagnac Field Hysteresis Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac Hysteresis measurements
        """
        super(sagnacHysteresisGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_FieldHysteresis.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacFieldHysteresisProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.field_max = self.inputs.field_max.value()
        procedure.field_step = self.inputs.field_step.value()
        procedure.field_azimuth = self.inputs.field_azimuth.value()
        procedure.field_polar = self.inputs.field_polar.value()
        procedure.settling = self.inputs.settling.value()
        procedure.reverse = self.inputs.reverse.isChecked()

        procedure.apply_current = self.inputs.apply_current.isChecked()
        procedure.current = self.inputs.current.value()*1e-3

        procedure.bias_field_x = self.inputs.bias_field_x.value()
        procedure.bias_field_y = self.inputs.bias_field_y.value()
        procedure.bias_field_z = self.inputs.bias_field_z.value()

        procedure.input_range = self.inputs.input_range.value()

        procedure.f_eom = self.inputs.f_eom.value()*1e6

        procedure.first_harm_order = self.inputs.first_harm_order.value()
        procedure.second_harm_order = self.inputs.second_harm_order.value()
        procedure.first_harm_tc = self.inputs.first_harm_tc.value()
        procedure.second_harm_tc = self.inputs.second_harm_tc.value()

        procedure.output_voltage = self.inputs.output_voltage.value()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure
    
    def make_current_sweep(self, currents):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """
        procedures = []
        for i in currents:
            procedure = self.make_procedure()
            procedure.apply_current = True
            procedure.current = i*1e-3
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures


    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        # create list of procedures to run
        do_sweep = self.inputs.do_current_sweep.isChecked()
        if do_sweep:
            # procedures = self.make_procedures()
            currents = np.arange(self.inputs.current_min.value(), self.inputs.current_max.value(), self.inputs.current_step.value())
            if self.inputs.current_max.value() not in currents:
                currents = np.append(currents,self.inputs.current_max.value())
            for x in currents:
                if x < 1e-5:
                    x = 0
            procedures = self.make_current_sweep(currents)
            # series_fname, series_header = self.start_series()
            # self.last_series_fname = series_fname
            # series_file = open(series_fname,'w')
            # series_file.write(series_header)
        else:
            procedures = [self.make_procedure()]

        for procedure in procedures:
            # ensure *some* sample name exists so Results.load() works
            if procedure.sample_name == '':
                procedure.sample_name = 'test'

            # create files
            pre = procedure.sample_name + \
                '_SagnacHyst_I{current:0.4f}mA_A{azimuth:0.1f}_P{polar:0.1f}_'.format(
                current=procedure.current*1e3,
                azimuth=procedure.field_azimuth,
                polar=procedure.field_polar
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
    window = sagnacHysteresisGUI()
    window.show()
    sys.exit(app.exec_())
