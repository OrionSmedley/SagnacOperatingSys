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
from sagnac.procedures import sagnacDCTiltProcedure

class sagnacDCTiltGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['sweep_field', 'sweep_field_azimuth']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacDCTiltGUI, self).__init__(
            procedure_class=sagnacDCTiltProcedure,
            displays=[
                'sample_name',
                'f_eom',
                'sweep_field',
                'sweep_field_step',
                'sweep_field_azimuth',
                'saturating_field',
                'saturating_field_polar',
                'bias_field_x',
                'bias_field_y',
                'bias_field_z'],
            x_axis='sweep_field',
            y_axis='ThetaK'
        )
        self.setWindowTitle('PyMeasure Sagnac DCTilt Hysteresis Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacDCTiltGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_DCTilt.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacDCTiltProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.current = self.inputs.applied_current.value()*1e-3
        procedure.settling = self.inputs.settling.value()
        procedure.wait = self.inputs.wait.value()

        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()

        procedure.hysteresis = self.inputs.hysteresis.isChecked()
        procedure.reverse = self.inputs.reverse.isChecked()
        procedure.pm_field = self.inputs.pm_field.isChecked()
        procedure.sweep_field = self.inputs.sweep_field.value()
        procedure.sweep_field_step = self.inputs.sweep_field_step.value()
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
                '_SagnacDCTilt_I{current:0.4f}mA_A{azimuth:0.1f}_'.format(
                current=procedure.current*1e3,
                azimuth=procedure.sweep_field_azimuth,
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
    window = sagnacDCTiltGUI()
    window.show()
    sys.exit(app.exec_())
