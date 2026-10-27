import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
import textwrap

import numpy as np

from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
from daedalus.procedures import Hall2HarmFixedIPFieldProcedure
from pymeasure.instruments.signalrecovery import DSP7265

from send_gmail import send_gmail

class daedalusHall2HarmFixedIPFieldGUI(ManagedWindow):

    def __init__(self):
        super(daedalusHall2HarmFixedIPFieldGUI, self).__init__(
            procedure_class=Hall2HarmFixedIPFieldProcedure,
            displays=[
                'sample_name',
                'field_IP_strength',
                'field_OOP_strength_start',
                'field_OOP_strength_end',
                'field_OOP_strength_step',
                'field_azimuth',
                'applied_voltage'
                ],
            x_axis='OOP_field_strength',
            y_axis='X1'
        )
        self.setWindowTitle('PyMeasure 2 Harm Fixed IP field OOP field Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus AMR measurements
        """
        super(daedalusHall2HarmFixedIPFieldGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'custom_inputs/daedalus_gui_2HarmonicFixedIPField.ui'))

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = Hall2HarmFixedIPFieldFieldProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.field_IP_strength = self.inputs.IP_field_strength.value()
        procedure.field_OOP_strength_start = self.inputs.OOP_field_start.value()
        procedure.field_OOP_strength_end = self.inputs.OOP_field_end.value()
        procedure.field_OOP_strength_step = self.inputs.OOP_field_step.value()
        procedure.field_swap = self.inputs.field_swap.isChecked()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms

        # this probably won't change much, so not in inputs to avoid confusion
        procedure.mag_calib_name = os.path.join(self.run_directory,'calibrations/proj_field')

        procedure.field_azimuth = self.inputs.azimuth_start.value()
        procedure.applied_voltage = self.inputs.applied_voltage.value()*1e-3 #mV

        procedure.sensitivity1 = DSP7265.SENSITIVITIES[self.inputs.sensitivity1.currentIndex()]
        procedure.sensitivity2 = DSP7265.SENSITIVITIES[self.inputs.sensitivity2.currentIndex()]
        procedure.time_constant1 = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()] # enforcing the same makes sense
        procedure.time_constant2 = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()] # enforcing the same makes sense

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_azimuth_sweep(self):
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
            procedure = self.make_procedure()
            procedure.field_azimuth = angle
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
        pre = sname + '_HallFixedIPField_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,suffix=suf,dated_folder=True,ext='txt')
        series_header = '# swept procedure column: oop_field_strength\n'
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
        procedures = self.make_procedures()
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
            pre = procedure.sample_name + '_HallFixedIPField_IPfield{ip_field:04.1f}_A{azimuth:05.1f}_'.format(ip_field=procedure.field_IP_strength,
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
                    There are no more queued Hall Field Sweep measurements on the Daedalus setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    IP Field: {ip_field:g} T
                    Applied Voltage: {volt:g} V

                    Please update parameters or finish your measurement.
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        ip_field=experiment.procedure.field_IP_strength,
                        volt=experiment.procedure.applied_voltage)
                    )
            elif not self.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    A Hall Field Sweep measurement has finished on the Daedalus setup. The
                    parameters of this scan were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    IP Field: {ip_field:g} T
                    Applied Voltage: {volt:g} V
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        ip_field=experiment.procedure.field_IP_strength,
                        volt=experiment.procedure.applied_voltage)
                    )
        if send_message:
            subject = '[Hall Field] Measurement finished on Daedalus Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusHall2HarmFixedIPFieldGUI()
    window.show()
    sys.exit(app.exec_())
