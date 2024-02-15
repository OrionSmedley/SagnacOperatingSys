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
from sagnac.procedures import sagnacDCHysteresisProcedure

class sagnacDCHysteresisGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['bias_field', 'bias_field_azimuth']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacDCHysteresisGUI, self).__init__(
            procedure_class=sagnacDCHysteresisProcedure,
            displays=[
                'sample_name',
                'f_eom',
                'current_max',
                'current_step',
                'saturating_field',
                'bias_field',
                'bias_field_azimuth'],
            x_axis='applied_current',
            y_axis='RatioR'
        )
        self.setWindowTitle('PyMeasure Sagnac DC Hysteresis Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacDCHysteresisGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_DCHysteresis.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacDCHysteresisProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.current_max = self.inputs.current_max.value()*1e-3
        procedure.current_step = self.inputs.current_step.value()*1e-3
        procedure.reverse = self.inputs.reverse.isChecked()
        procedure.hysteresis = self.inputs.hysteresis.isChecked()
        procedure.settling = self.inputs.settling.value()

        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()

        procedure.bias_field = self.inputs.bias_field.value()
        procedure.bias_field_azimuth = self.inputs.bias_field_azimuth.value()
        procedure.bias_field_polar = self.inputs.bias_field_polar.value()

        procedure.input_range = self.inputs.input_range.value()
        procedure.imp50 = self.inputs.imp50.isChecked()

        procedure.f_eom = self.inputs.f_eom.value()*1e6

        procedure.first_harm_order = self.inputs.first_harm_order.value()
        procedure.second_harm_order = self.inputs.second_harm_order.value()
        procedure.first_harm_tc = self.inputs.first_harm_tc.value()
        procedure.second_harm_tc = self.inputs.second_harm_tc.value()

        procedure.output_voltage = self.inputs.output_voltage.value()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure
    
    def make_bias_field_sweep(self, bias_fields, bias_field_azimuth):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """
        procedures = []
        for bias in bias_fields:
            procedure = self.make_procedure()
            procedure.bias_field = bias
            procedure.bias_field_azimuth = bias_field_azimuth
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    # def make_bias_field_azimuth_sweep(self, bias_field_azimuths, bias_field):
    #     """
    #     Makes a series of procedures varying bias field angle at a given bias field
    #     """
    #     procedures = []
    #     for ang in bias_field_azimuths:
    #         procedure = self.make_procedure()
    #         procedure.bias_field_azimuth = ang
    #         procedure.bias_field = bias_field
    #         procedure.first = False
    #         procedure.last = False
    #         procedures.append(procedure)
    #     return procedures

    # def make_procedures(self):
    #     """
    #     Constructs a series of procedures based on gui options
    #     """
    #     procedures = []

    #     # Number of parameters which can vary. Change this if more are added!
    #     # self.NUM_SWEEP_PARAMS = 2

    #     # make arrays of all of the possible parameter values we want
    #     bias_fields = np.arange(self.inputs.bias_field_start.value(), self.inputs.bias_field_stop.value(), self.inputs.bias_field_step.value())
    #     if self.inputs.bias_field_stop.value() not in bias_fields: # ensure we capture the endpoint
    #         bias_fields = np.append(bias_fields,self.inputs.bias_field_stop.value())
        
    #     bias_field_azimuths = np.arange(self.inputs.bias_field_azimuth_start.value(), self.inputs.bias_field_azimuth_stop.value(), self.inputs.bias_field_azimuth_step.value())
    #     if self.inputs.bias_field_azimuth_stop.value() not in bias_field_azimuths: # ensure we capture the endpoint
    #         bias_field_azimuths = np.append(bias_field_azimuths,self.inputs.bias_field_azimuth_stop.value())

    #     # make lists of them where the index of the list is the index of the
    #     # combobox or tab which corresponds to them
    #     sweep_values = [bias_fields, bias_field_azimuths]
    #     # Need separate start values in case we're not sweeping and start
    #     # is larger than stop in UI
    #     start_values = [self.inputs.bias_field_start.value(), self.inputs.bias_field_azimuth_start.value()]
    #     no_sweep_values = [self.inputs.bias_field.value(), self.inputs.bias_field_azimuth.value()]

    #     used_pnames = []
    #     used_pvals = []
    #     sweep_param_indices = {}
    #     for gui_item in dir(self.inputs):
    #         if gui_item.startswith('sweep_param_'):
    #             item_number = int(gui_item.split('_')[-1])
    #             sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex()

    #     if self.inputs.do_sweeps.isChecked():
    #         used_indices = [] # keeping track of which parameters swept so no repeats
    #         for param_number in sorted(sweep_param_indices.keys()): # programattically add all sweep parameter values
    #             param_index = sweep_param_indices[param_number]
    #             if param_index != self.NUM_SWEEP_PARAMS and param_index not in used_indices: # only care if not None
    #                 used_indices.append(param_index)
    #                 used_pnames.append(self.SWEEP_PARAM_NAMES[param_index])
    #                 used_pvals.append(sweep_values[param_index])
    #         # add on any that weren't swept
    #         for i in range(self.NUM_SWEEP_PARAMS):
    #             if i not in used_indices:
    #                 used_pvals.append([start_values[i]])
    #                 used_pnames.append(self.SWEEP_PARAM_NAMES[i])
    #         # Reverse order so that product gives us what we want
    #         used_pvals = used_pvals[::-1]
    #         used_pnames = used_pnames[::-1]
    #     else:
    #         for i in range(self.NUM_SWEEP_PARAMS):
    #             used_pnames.append(self.SWEEP_PARAM_NAMES[i])
    #             used_pvals.append([no_sweep_values[i]])

    #     # make a cartesian product of all of the swept values
    #     pvals = product(*used_pvals)
    #     for val_combo in pvals:
    #         # for each parameter combination, create a procedure and set the
    #         # appropriate parameter values
    #         procedure = self.make_procedure()
    #         for i, _ in enumerate(val_combo):
    #             setattr(procedure, used_pnames[i], val_combo[i])
    #         procedures.append(procedure)

    #     # Set first and last procedures to make sweeps faster and have less
    #     # voltage, field and angle oscillations.
    #     procedures[0].first = True
    #     procedures[-1].last = True

    #     return procedures

    # def start_series(self):
    #     """
    #     Creates the header and filename of the series file for these scans.
    #     """
    #     # ensure we have some sample name
    #     sname = self.inputs.sample_name.text()
    #     if sname == '':
    #         sname = 'undefined'
    #     pre = sname + '_DCHyst_series_'
    #     suf = ''
    #     series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
    #                                    suffix=suf,dated_folder=True,ext='txt')

    #     bias_field_section = '# Bias Field Start: %g deg\n'%self.inputs.bias_field_start.value()
    #     bias_field_section += '# Bias Field Stop: %g deg\n'%self.inputs.bias_field_stop.value()
    #     bias_field_section += '# Bias Field Step: %g deg\n'%self.inputs.bias_field_step.value()

    #     bias_field_azimuth_section = '# Bias Field Azimuth Start: %g deg\n'%self.inputs.bias_field_azimuth_start.value()
    #     bias_field_azimuth_section += '# Bias Field Azimuth Stop: %g deg\n'%self.inputs.bias_field_azimuth_stop.value()
    #     bias_field_azimuth_section += '# Bias Field Azimuth Step: %g deg\n'%self.inputs.bias_field_azimuth_step.value()

    #     series_header = '# swept procedure column: applied_current\n'
    #     sweep_sections = [bias_field_section, bias_field_azimuth_section, None]
    #     used_sections = []
    #     sweep_param_indices = {}

    #     # adding sections pertaining to sweeps
    #     for gui_item in dir(self.inputs):
    #         if gui_item.startswith('sweep_param_'):
    #             item_number = int(gui_item.split('_')[-1])
    #             sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex()
    #     if self.inputs.do_sweeps.isChecked():
    #         used_indices = [] # keeping track of which parameters swept so no repeats
    #         for param_number in sorted(sweep_param_indices.keys()): # programattically add all sweep sections
    #             param_index = sweep_param_indices[param_number]
    #             if param_index != self.NUM_SWEEP_PARAMS and param_index not in used_indices: # only care if not None
    #                 series_header += '# swept series parameter: %s\n'%self.SWEEP_PARAM_NAMES[param_index]
    #                 used_sections.append(sweep_sections[param_index])
    #         series_header += '# Parameters:\n#\n'
    #         for section in used_sections:
    #             series_header += section
    #     series_header += '#\n# Files in Series:\n#\n'
    #     return series_fname, series_header

    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        # create list of procedures to run
        do_sweep = self.inputs.do_sweeps.isChecked()
        if do_sweep:
            # procedures = self.make_procedures()
            bias_fields = np.arange(self.inputs.bias_field_start.value(), self.inputs.bias_field_stop.value(), self.inputs.bias_field_step.value())
            if self.inputs.bias_field_stop.value() not in bias_fields:
                bias_fields = np.append(bias_fields,self.inputs.bias_field_stop.value())
            for x in bias_fields:
                if x < 1e-5:
                    x = 0
            procedures = self.make_bias_field_sweep(bias_fields,self.inputs.bias_field_azimuth.value())
            # series_fname, series_header = self.start_series()
            # self.last_series_fname = series_fname
            # series_file = open(series_fname,'w')
            # series_file.write(series_header)
        else:
            procedures = [self.make_procedure()]

        for procedure in procedures:
            # ensure *some* sample name exists so Results.load() works
            if procedure.sample_name == '':
                procedure.sample_name = 'undefined'

            # create files
            pre = procedure.sample_name + '_DCHyst_B{bias:0.4f}_A{azimuth:0.1f}_'.format(
                bias=procedure.bias_field,
                azimuth=procedure.bias_field_azimuth,
            )
            suf = ''
            filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                       prefix=pre)

            # if do_sweep:
            #     series_file.write(os.path.split(filename)[-1] + '\n')

            # Queue experiment
            results = Results(procedure,filename)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)
        # if do_sweep:
        #     series_file.close()

    def finished(self, experiment):
        super().finished(experiment)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = sagnacDCHysteresisGUI()
    window.show()
    sys.exit(app.exec_())
