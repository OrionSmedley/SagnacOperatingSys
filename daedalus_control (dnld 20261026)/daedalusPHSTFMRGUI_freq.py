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
from daedalus.procedures import PHSTFMRProcedure_freq
from pymeasure.instruments.signalrecovery import DSP7265

from send_gmail import send_gmail

SENSE_MODES = ['A','-B','A-B']

class daedalusPHSTFMRGUI_freq(ManagedWindow):

    # Names of the procedure parameters which can be swept
    SWEEP_PARAM_NAMES = ['field_azimuth', 'dc_bias', 'field_strength']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super(daedalusPHSTFMRGUI_freq, self).__init__(
            procedure_class=PHSTFMRProcedure_freq,
            displays=[
                'sample_name',
                'AM_modulation',
                'field_polar',
                'field_azimuth',
                'field_strength',
                'saturate',
                'freq_start',
                'freq_end',
                'rf_power'],
            x_axis='rf_freq',
            y_axis='X'
        )
        self.setWindowTitle('PyMeasure PHSTFMR Frequency Scan')
        self.last_series_fname = None

    def identifySystem(self):
        hostname = socket.gethostname()
        return hostname

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus STFMR measurements
        """
        super(daedalusPHSTFMRGUI_freq, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/daedalus_gui_PHSTFMR_freq.ui'))
        self.inputs.station_name.setText(self.system)
        if self.system == 'icarus':
            self.inputs.save_dir.setText("C:\\Users\\TopMob\\Data\\junk")
        elif self.system == 'daedalus':
            self.inputs.save_dir.setText("F:\\junk")
        self.inputs.calib_file.setText('./calibrations/' + self.system)

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = PHSTFMRProcedure_freq()
        procedure.sample_name = self.inputs.sample_name.text()
        procedure.calib_file = self.inputs.calib_file.text()
        procedure.station_name = self.identifySystem()

        procedure.freq_start = self.inputs.frequency_start.value()
        procedure.freq_end = self.inputs.frequency_end.value()
        procedure.freq_step = self.inputs.frequency_step.value()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms
        procedure.field_azimuth = self.inputs.azimuth_start.value()
        procedure.field_polar = self.inputs.polar_angle.value()

        procedure.field_strength = self.inputs.field_strength_start.value()
        procedure.field_saturation = self.inputs.field_saturation.value()
        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.rf_power = self.inputs.rf_power.value()
        procedure.AM_modulation = self.inputs.am_modulation.isChecked()

        procedure.sensitivityL = DSP7265.SENSITIVITIES[self.inputs.sensitivityL.currentIndex()]
        procedure.time_constantL = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]
        procedure.lockin_phaseL = self.inputs.phaseL.value()
        procedure.lockin_ac_gainL = self.inputs.lockin_ac_gainL.value()
        procedure.lockin_sense_modeL = SENSE_MODES[self.inputs.lockin_sense_modeL.currentIndex()]
        
        procedure.sensitivityT = DSP7265.SENSITIVITIES[self.inputs.sensitivityT.currentIndex()]
        procedure.time_constantT = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]
        procedure.lockin_phaseT = self.inputs.phaseT.value()
        procedure.lockin_ac_gainT = self.inputs.lockin_ac_gainT.value()
        procedure.lockin_sense_modeT = SENSE_MODES[self.inputs.lockin_sense_modeT.currentIndex()]

        procedure.use_bias = self.inputs.use_bias.isChecked()
        if procedure.use_bias:
            procedure.dc_bias = self.inputs.bias_start.value()*1e-6 # uA
        else:
            procedure.dc_bias = 0.0

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_freq_sweep(self, field_strengths, angle, bias):
        """
        Makes a series of procedures varying field_strength at a given angle
        """
        procedures = []
        for field_strength in field_strengths:
            procedure = self.make_procedure()
            procedure.field_strength = field_strength
            procedure.field_azimuth = angle
            procedure.dc_bias = bias
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    def make_angle_sweep(self, angles, field_strength, bias):
        """
        Makes a series of procedures varying angle at a given field_strength
        """
        procedures = []
        for angle in angles:
            procedure = self.make_procedure()
            procedure.field_azimuth = angle
            procedure.field_strength = field_strength_start
            procedure.dc_bias = bias
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    def make_bias_sweep(self, biases, field_strength, angle):
        """
        Makes a series of procedures varying dc bias current
        """
        procedures = []
        for bias in biases:
            procedure = self.make_procedure()
            procedure.field_azimuth = angle
            procedure.field_strength = field_strength_start
            procedure.dc_bias = bias
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    def make_procedures(self):
        """
        Constructs a series of procedures based on gui options
        """
        procedures = []

        # Number of parameters which can vary. Change this if more are added!
        self.NUM_SWEEP_PARAMS = 3

        # make arrays of all of the possible parameter values we want
        field_strengths = np.arange(self.inputs.field_strength_start.value(), self.inputs.field_strength_end.value(), self.inputs.field_strength_step.value())
        if self.inputs.field_strength_end.value() not in field_strengths: # ensure we capture the endpoint
            field_strengths = np.append(field_strengths,self.inputs.field_strength_end.value())
        angles = np.arange(self.inputs.azimuth_start.value(), self.inputs.azimuth_end.value(), self.inputs.azimuth_step.value())
        if self.inputs.azimuth_end.value() not in angles: # ensure we capture the endpoint
            angles = np.append(angles,self.inputs.azimuth_end.value())
        biases = np.arange(self.inputs.bias_start.value(), self.inputs.bias_end.value()+self.inputs.bias_step.value(), self.inputs.bias_step.value())
        biases *= 1e-6 # uA

        # make lists of them where the index of the list is the index of the
        # combobox or tab which corresponds to them
        sweep_values = [angles, biases, field_strengths]
        # Need separate start values in case we're not sweeping and start
        # is larger than stop in UI
        start_values = [self.inputs.azimuth_start.value(), self.inputs.bias_start.value()*1e-6, self.inputs.field_strength_start.value()]

        used_pnames = []
        used_pvals = []
        sweep_param_indices = {}
        for gui_item in dir(self.inputs):
            if gui_item.startswith('sweep_param_'):
                item_number = int(gui_item.split('_')[-1])
                sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex() # TODO: does this work?
        if self.inputs.do_sweeps.isChecked():
            used_indices = [] # keeping track of which parameters swept so no repeats
            for param_number in sorted(sweep_param_indices.keys()): # programattically add all sweep parameter values
                param_index = sweep_param_indices[param_number]
                if param_index != self.NUM_SWEEP_PARAMS and param_index not in used_indices: # only care if not None
                    used_indices.append(param_index)
                    used_pnames.append(self.SWEEP_PARAM_NAMES[param_index])
                    used_pvals.append(sweep_values[param_index])
            # add on any that weren't swept
            for i in range(self.NUM_SWEEP_PARAMS):
                if i not in used_indices:
                    used_pvals.append([start_values[i]])
                    used_pnames.append(self.SWEEP_PARAM_NAMES[i])
            # Reverse order so that product gives us what we want
            used_pvals = used_pvals[::-1]
            used_pnames = used_pnames[::-1]
        else:
            for i in range(self.NUM_SWEEP_PARAMS):
                used_pnames.append(self.SWEEP_PARAM_NAMES[i])
                used_pvals.append([start_values[i]])

        # make a cartesian product of all of the swept values
        pvals = product(*used_pvals)
        for val_combo in pvals:
            # for each parameter combination, create a procedure and set the
            # appropriate parameter values
            procedure = self.make_procedure()
            for i, val in enumerate(val_combo):
                setattr(procedure, used_pnames[i], val_combo[i])
            procedures.append(procedure)

        # Set first and last procedures to make sweeps faster and have less
        # voltage, field and angle oscillations.
        procedures[0].first = True
        procedures[-1].last = True

        return procedures

    def start_series(self):
        """
        Creates the header and filename of the series file for these scans.
        """
        # ensure we have some sample name
        sname = self.inputs.sample_name.text()
        if sname == '':
            sname = 'undefined'
        pre = sname + '_STFMR_freq_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                       suffix=suf,dated_folder=True,ext='txt')

        angle_section = '# Initial Azimuthal Angle: %g deg\n'%self.inputs.azimuth_start.value()
        angle_section += '# Final Azimuthal Angle: %g deg\n'%self.inputs.azimuth_end.value()
        angle_section += '# Azimuthal Angle Step: %g deg\n'%self.inputs.azimuth_step.value()

        field_strength_section = '# Initial field_strength: %g GHz\n'%self.inputs.field_strength_start.value()
        field_strength_section += '# Final field_strength: %g GHz\n'%self.inputs.field_strength_end.value()
        field_strength_section += '# field_strength Step: %g GHz\n'%self.inputs.field_strength_step.value()

        bias_section = '# Initial DC Bias: %g A\n'%self.inputs.bias_start.value()
        bias_section += '# Final DC Bias: %g A\n'%self.inputs.bias_end.value()
        bias_section += '# DC Bias Step: %g A\n'%self.inputs.bias_step.value()

        series_header = '# swept procedure column: field_strength\n'
        sweep_sections = [angle_section, bias_section, field_strength_section, None]
        used_sections = []
        sweep_param_indices = {}

        # adding sections pertaining to sweeps
        for gui_item in dir(self.inputs):
            if gui_item.startswith('sweep_param_'):
                item_number = int(gui_item.split('_')[-1])
                sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex() # TODO: does this work?
        if self.inputs.do_sweeps.isChecked():
            used_indices = [] # keeping track of which parameters swept so no repeats
            for param_number in sorted(sweep_param_indices.keys()): # programattically add all sweep sections
                param_index = sweep_param_indices[param_number]
                if param_index != self.NUM_SWEEP_PARAMS and param_index not in used_indices: # only care if not None
                    series_header += '# swept series parameter: %s\n'%self.SWEEP_PARAM_NAMES[param_index]
                    used_sections.append(sweep_sections[param_index])
            series_header += '# Parameters:\n#\n'
            for section in used_sections:
                series_header += section
        else:
            for i in range(self.NUM_SWEEP_PARAMS):
                used_pnames.append(self.SWEEP_PARAM_NAMES[i])
                used_pvals.append([start_values[i]])
        series_header += '#\n# Files in Series:\n#\n'
        return series_fname, series_header

    def queue(self):
        direc = self.inputs.save_dir.text()
        # create list of procedures to run
        procedures = self.make_procedures()
        do_sweep = self.inputs.do_sweeps.isChecked()
        if do_sweep:
            series_fname, series_header = self.start_series()
            self.last_series_fname = series_fname
            series_file = open(series_fname,'w')
            series_file.write(series_header)

        for procedure in procedures:
            # ensure *some* sample name exists so Results.load() works
            if procedure.sample_name == '':
                procedure.sample_name = 'undefined'

            # create files
            pre = procedure.sample_name + '_STFMR_freq_B{field_strength:04.3f}_P{polar:05.1f}_A{azimuth:05.1f}_DC{bias:05.1f}_SAT{sat:1.0f}_AM{mod:1.0f}_'.format(
                field_strength=procedure.field_strength,
                polar=procedure.field_polar,
                azimuth=procedure.field_azimuth,
                bias=procedure.dc_bias*1e6,
                sat=float(procedure.saturate),
                mod=float(procedure.AM_modulation)
            )
            suf = ''
            filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                       prefix=pre)

            if do_sweep:
                series_file.write(os.path.split(filename)[-1] + '\n')

            # Queue experiment
            results = Results(procedure,filename)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)
        if do_sweep:
            series_file.close()

    def finished(self, experiment):
        super().finished(experiment)
        send_message = False
        if len(self.inputs.notify_email.text()) > 0:
            if not self.manager.experiments.has_next():
                send_message = True
                message = textwrap.dedent("""\
                    There are no more queued DC Bias STFMR measurements on the Daedalus setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    field_strength: {field_strength:g} T
                    DC Bias: {bias:g} uA

                    Please update parameters or finish your measurement.
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        field_strength=experiment.procedure.field_strength,
                        bias=experiment.procedure.dc_bias*1e6)
                    )
            elif not self.inputs.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    A DC Bias STFMR measurement has finished on the Daedalus setup. The
                    parameters of this scan were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    field_strength: {field_strength:g} T
                    DC Bias: {bias:g} uA

                    Please update parameters or finish your measurement.
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        field_strength=experiment.procedure.field_strength,
                        bias=experiment.procedure.dc_bias*1e6)
                    )
        if send_message:
            subject = '[DC Bias STFMR] Measurement finished on Daedalus Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusPHSTFMRGUI_freq()
    window.show()
    sys.exit(app.exec_())
