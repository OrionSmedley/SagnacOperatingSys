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
from daedalus.procedures import Hall2HarmFieldLI6221Procedure, Hall2DualHarmFieldLI6221Procedure
from pymeasure.instruments.signalrecovery import DSP7265

from send_gmail import send_gmail

SENSE_MODES = ['A','-B','A-B']
LOCKIN_SETUPS = ['single','dual']
FIELD_SWAP = ['None', 'Hysteretic', 'Maximum']

class daedalusHall2HarmFieldLI6221GUI(ManagedWindow):

    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super(daedalusHall2HarmFieldLI6221GUI, self).__init__(
            procedure_class=Hall2HarmFieldLI6221Procedure,
            displays=[
                'sample_name',
                'field_strength_start',
                'field_strength_end',
                'field_strength_step',
                'field_polar',
                'field_azimuth',
                'ac_current',
                'dc_bias'
                ],
            x_axis='field_strength',
            y_axis='X1'
        )
        self.setWindowTitle('PyMeasure 2Harm Field Scan')
        self.last_series_fname = None
        

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus AMR measurements
        """
        super(daedalusHall2HarmFieldLI6221GUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'custom_inputs/daedalus_gui_2HarmFieldLI6221.ui'))
        self.inputs.station_name.setText(self.system)
        if self.system == 'icarus':
            self.inputs.save_dir.setText("C:\\Users\\TopMob\\Data\\junk")
        elif self.system == 'daedalus':
            self.inputs.save_dir.setText("G:\\junk")
        self.inputs.calib_file.setText('./calibrations/' + self.system)

    def make_procedure(self, proc_type='dual'):
        """
        Constructs a single procedure.
        proc_type determines whether there are two lockins in single harmonic or
        one lockin in dual harmonic mode
        """
        
        if proc_type == 'single':
            procedure = Hall2HarmFieldLI6221Procedure()
            procedure.lockin_ac_gain1 = self.inputs.lockin_ac_gain1.value()
            procedure.lockin_ac_gain2 = self.inputs.lockin_ac_gain2.value()
            procedure.lockin_sense_mode1 = SENSE_MODES[self.inputs.lockin_sense_mode1.currentIndex()]
            procedure.lockin_sense_mode2 = SENSE_MODES[self.inputs.lockin_sense_mode2.currentIndex()]
        elif proc_type == 'dual':
            procedure = Hall2DualHarmFieldLI6221Procedure()
            procedure.lockin_ac_gain = self.inputs.lockin_ac_gain1.value()
            procedure.lockin_sense_mode = SENSE_MODES[self.inputs.lockin_sense_mode1.currentIndex()]

        procedure.sample_name = self.inputs.sample_name.text()
        procedure.calib_file = self.inputs.calib_file.text()
        procedure.station_name = self.system

        procedure.field_strength_start = self.inputs.field_start.value()
        procedure.field_strength_end = self.inputs.field_end.value()
        procedure.field_strength_step = self.inputs.field_step.value()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms
        procedure.field_swap = FIELD_SWAP[self.inputs.field_swap.currentIndex()]

        procedure.field_azimuth = self.inputs.azimuth_start.value()
        # procedure.applied_voltage = self.inputs.applied_voltage.value()*1e-3 #mV
        procedure.ac_current = self.inputs.ac_current.value()*1e-6 #uA
        procedure.dc_bias = self.inputs.dc_bias.value()*1e-6 #uA
        procedure.field_polar = self.inputs.polar_field.value()

        procedure.lockin_frequency = self.inputs.lockin_freq.value()

        procedure.sensitivity1 = DSP7265.SENSITIVITIES[self.inputs.sensitivity1.currentIndex()]
        procedure.time_constant1 = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]
        procedure.lockin_phase1 = self.inputs.lockin_phase1.value()
        
        procedure.sensitivity2 = DSP7265.SENSITIVITIES[self.inputs.sensitivity2.currentIndex()]
        procedure.time_constant2 = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]
        procedure.lockin_phase2 = self.inputs.lockin_phase2.value()

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_azimuth_sweep(self, proc_type):
        """
        Makes a series of procedures varying frequency at a given angle
        """
        procedures = []
        angles = np.arange(self.inputs.azimuth_start.value(),
                           self.inputs.azimuth_end.value(),
                           self.inputs.azimuth_step.value())
        if self.inputs.azimuth_end.value() not in angles: # to catch the last one
            angles = np.append(angles, self.inputs.azimuth_end.value())
        for angle in angles:
            procedure = self.make_procedure(proc_type)
            procedure.field_azimuth = angle
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)

        # Set first and last procedures to make sweeps faster and have less
        # voltage, field and angle oscillations.
        procedures[0].first = True
        procedures[-1].last = True

        return procedures

    def make_procedures(self, proc_type):
        """
        Constructs a series of procedures based on gui options
        """
        procedures = []

        if self.inputs.do_azimuth_sweep.isChecked():
            procedures = self.make_azimuth_sweep(proc_type)
        else:
            procedures.append(self.make_procedure(proc_type))

        return procedures

    def start_series(self):
        """
        Creates the header and filename of the series file for these scans.
        """
        # ensure we have some sample name
        sname = self.inputs.sample_name.text()
        if sname == '':
            sname = 'undefined'
        pre = sname + '_HallField_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,suffix=suf,dated_folder=True,ext='txt')
        series_header = '# swept procedure column: field_strength\n'
        series_header += '# swept series parameter: field_azimuth\n'
        series_header += '# Parameters:\n#\n'
        series_header += '# Initial Angle: %.2f deg\n'%self.inputs.azimuth_start.value()
        series_header += '# Final Angle: %.2f deg\n'%self.inputs.azimuth_end.value()
        series_header += '# Angle Step: %.2f deg\n'%self.inputs.azimuth_step.value()
        series_header += '#\n# Files in Series:\n#\n'
        return series_fname, series_header

    def queue(self):
        direc = self.inputs.save_dir.text()
        # make list of procedures
        proc_type = LOCKIN_SETUPS[self.inputs.lockin_setup.currentIndex()]
        procedures = self.make_procedures(proc_type)
        do_sweep = self.inputs.do_azimuth_sweep.isChecked()
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
            pre = procedure.sample_name + '_HallField_P{polar:04.1f}_A{azimuth:05.1f}_'.format(polar=procedure.field_polar,
                                                                                               azimuth=procedure.field_azimuth)
            suf = ''
            filename = unique_filename(direc,dated_folder=True,suffix=suf,prefix=pre)
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
                    There are no more queued Hall Field Sweep measurements on the {system} setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    Applied Voltage: {volt:g} V

                    Please update parameters or finish your measurement.
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        volt=experiment.procedure.applied_voltage)
                    )
            elif not self.inputs.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    A Hall Field SweeDaedalusp measurement has finished on the {system} setup. The
                    parameters of thiDaedaluss scan were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    Applied Voltage: {volt:g} V
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        volt=experiment.procedure.applied_voltage)
                    )
        if send_message:
            subject = f'[Hall Field] Measurement finished on {self.system} Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusHall2HarmFieldLI6221GUI()
    window.show()
    sys.exit(app.exec_())
