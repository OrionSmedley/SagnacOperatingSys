import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
import textwrap
import socket
import numpy as np

from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
from sagnac.procedures import AMRAngProcedure
from pymeasure.instruments.signalrecovery import DSP7265

# from send_gmail import send_gmail

SENSE_MODES = ['A','-B','A-B']

class daedalusAMRAngGUI(ManagedWindow):

    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super().__init__(
            procedure_class=AMRAngProcedure,
            displays=[
                'sample_name',
                'field_azimuth_start',
                'field_azimuth_end',
                'field_azimuth_step',
                'field_strength',
                'applied_voltage'
                ],
            x_axis='field_azimuth',
            y_axis='X'
        )
        self.setWindowTitle('PyMeasure AMR Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus AMR measurements
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'custom_inputs/daedalus_gui_AMRAng.ui'))

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = AMRAngProcedure()
        procedure.sample_name = self.inputs.sample_name.text()
        procedure.station_name = self.system

        procedure.field_azimuth_start = self.inputs.azimuth_start.value()
        procedure.field_azimuth_end = self.inputs.azimuth_end.value()
        procedure.field_azimuth_step = self.inputs.azimuth_step.value()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms

        procedure.field_strength = self.inputs.field_start.value()
        procedure.applied_voltage = self.inputs.applied_voltage.value()*1e-3 #mV
        procedure.field_polar = self.inputs.polar_field.value()

        procedure.sensitivity = DSP7265.SENSITIVITIES[self.inputs.sensitivity.currentIndex()]
        procedure.time_constant = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]
        procedure.lockin_ac_gain = self.inputs.lockin_ac_gain.value()
        procedure.lockin_frequency = self.inputs.lockin_freq.value()
        procedure.lockin_phase = self.inputs.lockin_phase.value()
        procedure.lockin_sense_mode = SENSE_MODES[self.inputs.lockin_sense_mode.currentIndex()]

        # R1 and R3 effectively hard-coded, non-interactible in UI
        procedure.wheatsone_R1 = self.inputs.wheatstone_R1.value() # 1886 Ohm
        procedure.wheatsone_R2 = self.inputs.wheatstone_R2.value()
        procedure.wheatsone_R3 = self.inputs.wheatstone_R3.value() # 1936 Ohm

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_field_sweep(self):
        """
        Makes a series of procedures varying frequency at a given angle
        """
        procedures = []
        fields = np.arange(self.inputs.field_start.value(),
                           self.inputs.field_end.value(),
                           self.inputs.field_step.value())
        if self.inputs.field_end.value() not in fields:
            fields = np.append(fields, self.inputs.field_end.value())
        for field in fields:
            procedure = self.make_procedure()
            procedure.field_strength = field
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)

        # Set first and last procedures to make sweeps faster and have less
        # voltage, field and angle oscillations.
        procedures[0].first = True
        procedures[-1].last = True

        return procedures

    def make_procedures(self):
        """
        Constructs a series of procedures based on gui options
        """
        procedures = []

        if self.inputs.do_field_sweep.isChecked():
            procedures = self.make_field_sweep()
        else:
            procedures.append(self.make_procedure())

        return procedures

    def start_series(self):
        """
        Creates the header and filename of the series file for these scans.
        """
        # ensure we have some sample name
        sname = self.inputs.sample_name.text()
        if sname == '':
            sname = 'undefined'
        pre = sname + '_AMRAng_Field_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                       suffix=suf,dated_folder=True,ext='txt')
        series_header = '# swept procedure column: field_azimuth\n'
        series_header += '# swept series parameter: field_strength\n'
        series_header += '# Parameters:\n#\n'
        series_header += '# Initial Field: %.5f T\n'%self.inputs.field_start.value()
        series_header += '# Final Field: %.5f T\n'%self.inputs.field_end.value()
        series_header += '# Field Step: %.5f T\n'%self.inputs.field_step.value()
        series_header += '#\n# Files in Series:\n#\n'
        return series_fname, series_header

    def queue(self):
        direc = self.inputs.save_dir.text()
        # Make list of procedures
        procedures = self.make_procedures()
        do_sweep = self.inputs.do_field_sweep.isChecked()
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
            pre = procedure.sample_name + '_AMRAng_P{polar:04.1f}_B{field:07.5f}_'.format(polar=procedure.field_polar, field=procedure.field_strength)
            suf = ''
            filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                       prefix=pre)
            if do_sweep:
                series_file.write(os.path.split(filename)[-1] + '\n')

            # Queue experiment
            results = Results(procedure,filename)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)
        if self.inputs.do_field_sweep.isChecked():
            series_file.close()

    def finished(self, experiment):
        super().finished(experiment)
        # send_message = False
        # if len(self.inputs.notify_email.text()) > 0:
        #     if not self.manager.experiments.has_next():
        #         send_message = True
        #         message = textwrap.dedent("""\
        #             There are no more queued AMR Angle Sweep measurements on the {system} setup.
        #             The last parameters ran were:

        #             Sample Name: {name}
        #             Field Strength: {field:g} T
        #             Polar Angle: {polar:g} deg
        #             Applied Voltage: {volt:g} V

        #             Please update parameters or finish your measurement.
        #             """.format(
        #                 system=self.system,
        #                 name=experiment.procedure.sample_name,
        #                 field=experiment.procedure.field_strength,
        #                 polar=experiment.procedure.field_polar,
        #                 volt=experiment.procedure.applied_voltage
        #                 )
        #             )
        #     elif not self.notify_at_end.isChecked():
        #         send_message = True
        #         message = textwrap.dedent("""\
        #             An AMR Angle Sweep measurement has finished on the {system} setup. The
        #             parameters of this scan were:

        #             Sample Name: {name}
        #             Field Strength: {field:g} T
        #             Polar Angle: {polar:g} deg
        #             Applied Voltage: {volt:g} V
        #             """.format(
        #                 system=self.system,
        #                 name=experiment.procedure.sample_name,
        #                 field=experiment.procedure.field_strength,
        #                 polar=experiment.procedure.field_polar,
        #                 volt=experiment.procedure.applied_voltage
        #                 )
        #             )
        # if send_message:
        #     subject = f'[AMR Angle] Measurement finished on {self.system} Setup'
        #     addresses = [str(self.inputs.notify_email.text())]
        #     files = []
        #     if self.last_series_fname is not None: # attach sweep file if appropriate
        #         files.append(self.last_series_fname)
        #     send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusAMRAngGUI()
    window.show()
    sys.exit(app.exec_())
