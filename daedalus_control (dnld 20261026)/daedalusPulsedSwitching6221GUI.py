import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
import textwrap
import socket
import numpy as np

from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
from daedalus.procedures import PulsedSwitching6221Procedure
from daedalus.custom_instruments import Keithley6221
from send_gmail import send_gmail

class daedalusPulsedSwitching6221GUI(ManagedWindow):

    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super().__init__(
            procedure_class=PulsedSwitching6221Procedure,
            displays=[
                'sample_name',
                'current_pulse_start',
                'current_pulse_end',
                'current_pulse_step',
                'field_strength_ip',
                'field_azimuth',
                'ac_current',
                'lockin_freq',
                'width'
                ],
            x_axis='current',
            y_axis='X1'
        )
        self.setWindowTitle('PyMeasure Current Pulse 6221 Scan')
        self.last_series_fname = None
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus Pulsed Switching measurements
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'custom_inputs/daedalus_gui_PulsedSwitching6221.ui'))
        self.inputs.station_name.setText(self.system)
        self.inputs.calib_file.setText('./calibrations/' + self.system)
    

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = PulsedSwitching6221Procedure()
        procedure.sample_name = self.inputs.sample_name.text()
        procedure.calib_file = self.inputs.calib_file.text()
        procedure.station_name = self.system

        procedure.ac_current = self.inputs.ac_current.value()*1e-6 #uA
        procedure.lockin_freq = self.inputs.lockin_freq.value()
        procedure.current_pulse_start = self.inputs.current_pulse_start.value()*1e-3
        procedure.current_pulse_end = self.inputs.current_pulse_end.value()*1e-3
        procedure.current_pulse_step = self.inputs.current_pulse_step.value()*1e-3
        procedure.width = self.inputs.width.value()*1e-6
        procedure.field_strength_ip = self.inputs.field_strength_ip.value()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms

        # this probably won't change much, so not in inputs to avoid confusion
        #procedure.mag_calib_name = os.path.join(self.run_directory,'calibrations/icarus')
        procedure.field_azimuth = self.inputs.azimuth_start.value()
        procedure.sensitivity = DSP7265.SENSITIVITIES[self.inputs.sensitivity.currentIndex()]
        procedure.time_constant = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]
        # Adding the pulse generator inputs
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_azimuth_sweep(self):
        """
        Makes a series of procedures varying azimuth
        """
        procedures = []
        angles = np.arange(self.inputs.azimuth_start.value(),
                           self.inputs.azimuth_end.value(),
                           self.inputs.azimuth_step.value())
        if self.inputs.azimuth_end.value() not in angles: # to catch the last one
            angles = np.append(angles, self.inputs.azimuth_end.value())
        for angle in angles:
            procedure = self.make_procedure()
            procedure.field_azimuth = angle
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)

        # Set first and last procedures to make sweeps faster and have less
        # current, field and angle oscillations.
        procedures[0].first = True
        procedures[-1].last = True

        return procedures

    def make_procedures(self):
        """
        Constructs a series of procedures based on gui options
        """
        procedures = []
        if self.inputs.do_azimuth_sweep.isChecked():
            procedures = self.make_azimuth_sweep()
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
        pre = sname + '_CurrentSwitching_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                       suffix=suf,dated_folder=True,ext='txt')
        series_header = '# swept procedure column: field_strength\n'

        if self.inputs.do_azimuth_sweep.isChecked():
            series_header += '# swept series parameter: field_azimuth\n'
            series_header += '# Parameters:\n#\n'
            series_header += '# Initial Azimuth: %g T\n'%self.inputs.azimuth_start.value()
            series_header += '# Final Azimuth: %g T\n'%self.inputs.azimuth_end.value()
            series_header += '# Azimuth Step: %g T\n'%self.inputs.azimuth_step.value()
        series_header += '#\n# Files in Series:\n#\n'
        return series_fname, series_header

    def queue(self):
        direc = self.inputs.save_dir.text()
        # Make list of procedures
        procedures = self.make_procedures()
        if self.inputs.do_azimuth_sweep.isChecked():
            do_sweep = True
        else:
            do_sweep = False
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
            pre = procedure.sample_name + '_current_A{azimuth:05.1f}_IP{inplanefield:07.5f}_'.format(
                azimuth=procedure.field_azimuth,
                inplanefield=procedure.field_strength_ip,
            )
            suf = ''
            filename = unique_filename(direc, dated_folder=True, suffix=suf,
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
                    There are no more queued Current Sweep measurements on the {system} setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Lockin voltage: {volt:g} V
                    Inplane field: {inplanefield:g} T
                    Please update parameters or finish your measurement.
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        volt=experiment.procedure.lockin_voltage,
                        inplanefield=experiment.procedure.field_strength_ip,
                        )
                    )
            elif not self.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    An Pulsed Switching Field Sweep measurement has finlockinished on the {system} setup. The
                    parameters of this scan were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Inplane field: {inplanefield:g} T
                    Lockin voltage: {volt:g} V
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        volt=experiment.procedure.lockin_voltage,
                        inplanefield=experiment.procedure.field_strength_ip,
                        )
                    )
        if send_message:
            subject = f'[Pulsed Switching] Measurement finished on {self.system} Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusPulsedSwitching6221GUI()
    window.show()
    sys.exit(app.exec_())
