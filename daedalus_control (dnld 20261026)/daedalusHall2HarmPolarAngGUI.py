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
from daedalus.procedures import Hall2HarmPolarAngProcedure
from pymeasure.instruments.signalrecovery import DSP7265

from send_gmail import send_gmail

class daedalusHall2HarmPolarAngGUI(ManagedWindow):

    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super(daedalusHall2HarmPolarAngGUI, self).__init__(
            procedure_class=Hall2HarmPolarAngProcedure,
            displays=[
                'sample_name',
                'field_polar_start',
                'field_polar_end',
                'field_polar_step',
                'field_strength',
                'applied_voltage'
                ],
            x_axis='field_polar',
            y_axis='X2'
        )
        self.setWindowTitle('PyMeasure Second Harmonic Scan')
        self.last_series_fname = None
        

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus AMR measurements
        """
        super(daedalusHall2HarmPolarAngGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/daedalus_gui_2HarmonicPolarAng.ui'))
        self.inputs.station_name.setText(self.system)
        self.inputs.calib_file.setText('./calibrations/' + self.system)

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = Hall2HarmPolarAngProcedure()
        procedure.sample_name = self.inputs.sample_name.text()
        procedure.calib_file = self.inputs.calib_file.text()
        procedure.station_name = self.system

        procedure.field_polar_start = self.inputs.polar_start.value()
        procedure.field_polar_end = self.inputs.polar_end.value()
        procedure.field_polar_step = self.inputs.polar_step.value()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms

        procedure.field_strength = self.inputs.field_start.value()
        procedure.applied_voltage = self.inputs.applied_voltage.value()*1e-3 #mV
        procedure.field_azimuth = self.inputs.azimuth_field.value()

        procedure.sensitivity1 = DSP7265.SENSITIVITIES[self.inputs.sensitivity1.currentIndex()]
        procedure.sensitivity2 = DSP7265.SENSITIVITIES[self.inputs.sensitivity2.currentIndex()]
        procedure.time_constant1 = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()] # should probably enforce the same
        procedure.time_constant2 = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()] # should probably enforce the same

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_field_sweep(self):
        """
        Makes a series of procedures varying frequency at a given angle
        """
        procedures = []
        if self.inputs.field_start.value() <0 and self.inputs.field_end.value() <0:
            step = -1*np.abs(self.inputs.field_step.value())
        else:
            step = self.inputs.field_step.value()
        fields = np.arange(self.inputs.field_start.value(), self.inputs.field_end.value(), step)
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
        pre = sname + '_HallAngle_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                       suffix=suf,dated_folder=True,ext='txt')
        series_header = '# swept procedure column: field_polar\n'
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

            # Create files
            pre = procedure.sample_name + '_HallAngle_A{azimuth:04.1f}_B{field:07.5f}'.format(azimuth=procedure.field_azimuth,
                                                                                             field=procedure.field_strength)
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
        send_message = False
        if len(self.inputs.notify_email.text()) > 0:
            if not self.manager.experiments.has_next():
                send_message = True
                message = textwrap.dedent("""\
                    There are no more queued Hall Angle Sweep measurements on the {system} setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Field Strength: {field:g} T
                    Polar Angle: {polar:g} deg
                    Applied Voltage: {volt:g} V

                    Please update parameters or finish your measurement.
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        field=experiment.procedure.field_strength,
                        polar=experiment.procedure.field_polar,
                        volt=experiment.procedure.applied_voltage)
                    )
            elif not self.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    A Hall Angle Sweep measurement has finished on the {system} setup. The
                    parameters of this scan were:

                    Sample Name: {name}
                    Field Strength: {field:g} T
                    Azimuth Angle: {azimuth:g} deg
                    Applied Voltage: {volt:g} V
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        field=experiment.procedure.field_strength,
                        polar=experiment.procedure.field_azimuth,
                        volt=experiment.procedure.applied_voltage)
                    )
        if send_message:
            subject = f'[Hall Angle] Measurement finished on {self.system} Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusHall2HarmPolarAngGUI()
    window.show()
    sys.exit(app.exec_())
