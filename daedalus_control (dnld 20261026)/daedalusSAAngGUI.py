import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
from itertools import product
import textwrap
import socket
import time
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
from daedalus.procedures import SAAngProcedure
from pymeasure.instruments.agilent import Agilent8563E, Agilent8257D

import numpy as np

class daedalusSAFieldGUI(ManagedWindow):
    # Names of the procedure parameters which can be swept
    SWEEP_PARAM_NAMES = ['rf_frequency_start', 'field_strength']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super().__init__(
            procedure_class=SAFieldProcedure,
            displays=[
                'sample_name',
                'field_strength',
                'field_azimuth_start',
                'field_azimuth_end',
                'field_azimuth_step',
                'rf_frequency_start',
                'rf_power',
                'field_polar'],
            x_axis='field_azimuth',
            y_axis='A'
        )
        self.setWindowTitle('PyMeasure Spectrum Analyzer Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus Spectrum Analyzer measurements
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/daedalus_gui_SAAng.ui'))
        self.inputs.station_name.setText(self.system)
        if self.system == 'icarus':
            self.inputs.save_dir.setText("C:\\Users\\TopMob\\Data\\junk")
        elif self.system == 'daedalus':
            self.inputs.save_dir.setText("F:\\junk")
        self.inputs.calib_file.setText('./calibrations/' + self.system)

    def make_procedure(self):
        procedure = SAAngProcedure()

        procedure.sample_name = self.inputs.sample_name.text()
        procedure.station_name = self.system
        procedure.calib_file = self.inputs.calib_file.text()

        mults = np.array([1,1e3,1e6,1e9])
        procedure.rf_frequency_start = self.inputs.freq_start.value() *\
                                       mults[1:][self.inputs.freq_start_mult.currentIndex()]

        #procedure.sweep_time = self.inputs.sweep_time.value()
        procedure.zero_span = self.inputs.zero_span.isChecked()
        procedure.span = self.inputs.span.value() *\
                                       mults[self.inputs.span_mult.currentIndex()]
        procedure.resolution_bandwidth = self.inputs.rb.value() *\
                                       mults[self.inputs.rb_mult.currentIndex()]
        procedure.video_bandwidth = self.inputs.vb.value() *\
                                       mults[self.inputs.vb_mult.currentIndex()]


        procedure.rf_power = self.inputs.rf_power.value()
        procedure.AM_freq = self.inputs.AM_freq.value()*\
                            mults[self.inputs.AM_freq_mult.currentIndex()]

        procedure.field_strength = self.inputs.field_start.value()
        procedure.field_polar = self.inputs.polar_angle.value()
        procedure.field_azimuth_start = self.inputs.azimuth_start.value()
        procedure.field_azimuth_end = self.inputs.azimuth_end.value()
        procedure.field_azimuth_step = self.inputs.azimuth_step.value()

        procedure.delay = self.inputs.delay.value()*1e-3

        procedure.start_time = time.strftime("%Y-%m-%d %I:%M%p").lower()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_field_sweep(self, fields, angle):
        """
        Makes a series of procedures varying field at a given angle
        """
        procedures = []
        for field in fields:
            procedure = self.make_procedure()
            procedure.field_strength = field
            procedure.field_azimuth = angle
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    def make_freq_sweep(self, freqs, field):
        """
        Makes a series of procedures varying angle at a given field
        """
        procedures = []
        for freq in freqs:
            procedure = self.make_procedure()
            procedure.rf_frequency_start = freq
            procedure.field_strength = field
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
        self.NUM_SWEEP_PARAMS = 2

        # make arrays of all of the possible parameter values we want
        fields = np.arange(self.inputs.field_start.value(),
                            self.inputs.field_end.value(),
                            self.inputs.field_step.value())
        if self.inputs.field_end.value() not in fields: # ensure we capture the endpoint
            fields = np.append(fields,self.inputs.field_end.value())

        freqs = np.arange(self.inputs.freq_start.value()*mults[1:][self.inputs.freq_start_mult.currentIndex()],
                            self.inputs.freq_end.value()*mults[1:][self.inputs.freq_end_mult.currentIndex()],
                            self.inputs.freq_step.value()*mults[self.inputs.freq_step_mult.currentIndex()])
        if self.inputs.freq_end.value() not in freqs: # ensure we capture the endpoint
            freqs = np.append(freqs,self.inputs.freq_end.value())

        # make lists of them where the index of the list is the index of the
        # combobox or tab which corresponds to them
        sweep_values = [freqs, fields]
        # Need separate start values in case we're not sweeping and start
        # is larger than stop in UI
        start_values = [self.inputs.freq_start.value(),
                        self.inputs.field_start.value()]

        used_pnames = []
        used_pvals = []
        sweep_param_indices = {}
        for gui_item in dir(self.inputs):
            if gui_item.startswith('sweep_param_'):
                item_number = int(gui_item.split('_')[-1])
                sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex()
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
                setattr(procedure, used_pnames[i], val)
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
        pre = sname + '_SA_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                       suffix=suf,dated_folder=True,ext='txt')

        angle_section = '# Initial Azimuthal Angle: %g deg\n'%self.inputs.azimuth_start.value()
        angle_section += '# Final Azimuthal Angle: %g deg\n'%self.inputs.azimuth_end.value()
        angle_section += '# Azimuthal Angle Step: %g deg\n'%self.inputs.azimuth_step.value()

        frequency_section = '# Initial Field: %g T\n'%self.inputs.field_start.value()
        frequency_section += '# Final Field: %g T\n'%self.inputs.field_end.value()
        frequency_section += '# Field Step: %g T\n'%self.inputs.field_step.value()

        series_header = '# swept procedure column: freq_in\n'
        sweep_sections = [angle_section, field_section, None]
        used_sections = []
        sweep_param_indices = {}

        # adding sections pertaining to sweeps
        for gui_item in dir(self.inputs):
            if gui_item.startswith('sweep_param_'):
                item_number = int(gui_item.split('_')[-1])
                sweep_param_indices[item_number] = getattr(self.inputs, gui_item).currentIndex()
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
            pre = procedure.sample_name + '_SA_F{field:04.3f}_P{polar:05.1f}_A{azimuth:05.1f}_'.format(
                field=procedure.field_strength,
                polar=procedure.field_polar,
                azimuth=procedure.field_azimuth,
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
                    There are no more queued Spectrum Analyzer measurements on the setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    Field: {field:g} T

                    Please update parameters or finish your measurement.
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        field=experiment.procedure.field_strength)
                    )
            elif not self.inputs.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    A Spectrum Analyzer measurement has finished on the Daedalus setup. The
                    parameters of this scan were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    Field: {field:g} T

                    Please update parameters or finish your measurement.
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        field=experiment.procedure.field_strength)
                    )
        if send_message:
            subject = '[Spectrum Analyzer] Measurement finished on Daedalus Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusSAAngGUI()
    window.show()
    sys.exit(app.exec_())
