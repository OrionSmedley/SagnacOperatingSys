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
from daedalus.procedures import AMRFieldBiasHystProcedure
from pymeasure.instruments.signalrecovery import DSP7265

from send_gmail import send_gmail

class daedalusAMRFieldHystGUI(ManagedWindow):

    def __init__(self):
        super(daedalusAMRFieldHystGUI, self).__init__(
            procedure_class=AMRFieldBiasHystProcedure,
            displays=[
                'sample_name',
                'field_strength_start',
                'field_strength_end',
                'field_strength_step',
                'field_azimuth',
                'applied_voltage',
                'dc_bias'
                ],
            x_axis='field_strength',
            y_axis='X'
        )
        self.setWindowTitle('PyMeasure AMR Field Hysteresis Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus AMR measurements
        """
        super(daedalusAMRFieldHystGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'custom_inputs/daedalus_gui_AMRFieldHyst.ui'))

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = AMRFieldBiasHystProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.field_strength_start = self.inputs.field_start.value()
        procedure.field_strength_end = self.inputs.field_end.value()
        procedure.field_strength_step = self.inputs.field_step.value()
        procedure.field_swap = self.inputs.field_swap.isChecked()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms

        # this probably won't change much, so not in inputs to avoid confusion
        procedure.mag_calib_name = os.path.join(self.run_directory,'calibrations/proj_field')

        procedure.field_azimuth = self.inputs.azimuth_start.value()
        procedure.field_polar = self.inputs.polar_field.value()

        procedure.applied_voltage = self.inputs.applied_voltage.value()*1e-3 #mV
        procedure.sensitivity = DSP7265.SENSITIVITIES[self.inputs.sensitivity.currentIndex()]
        procedure.time_constant = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]

        # R1 and R3 effectively hard-coded, non-interactible in UI
        procedure.wheatsone_R1 = self.inputs.wheatstone_R1.value() # 1886 Ohm
        procedure.wheatsone_R2 = self.inputs.wheatstone_R2.value()
        procedure.wheatsone_R3 = self.inputs.wheatstone_R3.value() # 1936 Ohm

        procedure.use_bias = self.inputs.use_bias.isChecked()
        if procedure.use_bias:
            procedure.dc_bias = self.inputs.bias_start.value()*1e-6 # uA
        else:
            procedure.dc_bias = 0.0

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure

    def make_dc_sweep(self):
        """
        Makes a series of procedures varying the dc bias
        """
        procedures = []
        biases = np.arange(self.inputs.bias_start.value(),
                           self.inputs.bias_end.value(),
                           self.inputs.bias_step.value())
        if self.inputs.bias_end.value() not in biases: # to catch the last one
            biases = np.append(biases, self.inputs.bias_end.value())
        for bias in biases:
            procedure = self.make_procedure()
            procedure.dc_bias = bias*1e-6 #uA
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)

        # Set first and last procedures to make sweeps faster and have less
        # voltage, field and angle oscillations.
        procedures[0].first = True
        procedures[-1].last = True

        return procedures

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
        # voltage, field and angle oscillations.
        procedures[0].first = True
        procedures[-1].last = True

        return procedures

    def make_dc_azimuth_sweep(self):
        """
        Make a series of procedures varying azimuth and dc bias
        """
        procedures = []
        angles = np.arange(self.inputs.azimuth_start.value(),
                           self.inputs.azimuth_end.value(),
                           self.inputs.azimuth_step.value())
        biases = np.arange(self.inputs.bias_start.value(),
                           self.inputs.bias_end.value(),
                           self.inputs.bias_step.value())
        for angle in angles: # angles is the outer loop because that is faster
            for bias in biases:
                procedure = self.make_procedure()
                procedure.field_azimuth = angle
                procedure.dc_bias = bias*1e-6 #uA
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
        if self.inputs.do_azimuth_sweep.isChecked() and not \
           self.inputs.do_bias_sweep.isChecked():
            procedures = self.make_azimuth_sweep()
        if self.inputs.do_bias_sweep.isChecked() and not \
           self.inputs.do_azimuth_sweep.isChecked():
            procedures = self.make_dc_sweep()
        if self.inputs.do_bias_sweep.isChecked() and \
           self.inputs.do_azimuth_sweep.isChecked():
            procedures = self.make_dc_azimuth_sweep()
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
        pre = sname + '_AMRField_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                       suffix=suf,dated_folder=True,ext='txt')
        series_header = '# swept procedure column: field_strength\n'

        if self.inputs.do_azimuth_sweep.isChecked() and not \
           self.inputs.do_bias_sweep.isChecked():
            series_header += '# swept series parameter: field_azimuth\n'
            series_header += '# Parameters:\n#\n'
            series_header += '# Initial Azimuth: %g T\n'%self.inputs.azimuth_start.value()
            series_header += '# Final Azimuth: %g T\n'%self.inputs.azimuth_end.value()
            series_header += '# Azimuth Step: %g T\n'%self.inputs.azimuth_step.value()
        if self.inputs.do_bias_sweep.isChecked() and not \
           self.inputs.do_azimuth_sweep.isChecked():
            series_header += '# swept series parameter: dc_bias\n'
            series_header += '# Parameters:\n#\n'
            series_header += '# Initial DC bias: %g T\n'%self.inputs.bias_start.value()
            series_header += '# Final DC bias: %g T\n'%self.inputs.bias_end.value()
            series_header += '# DC bias step: %g T\n'%self.inputs.bias_step.value()
        elif self.inputs.do_bias_sweep.isChecked() and \
           self.inputs.do_azimuth_sweep.isChecked():
            series_header += '# swept series parameter: field_azimuth\n'
            series_header += '# Parameters:\n#\n'
            series_header += '# Initial Azimuth: %g T\n'%self.inputs.azimuth_start.value()
            series_header += '# Final Azimuth: %g T\n'%self.inputs.azimuth_end.value()
            series_header += '# Azimuth Step: %g T\n'%self.inputs.azimuth_step.value()
            series_header += '# Initial DC bias: %g T\n'%self.inputs.bias_start.value()
            series_header += '# Final DC bias: %g T\n'%self.inputs.bias_end.value()
            series_header += '# DC bias step: %g T\n'%self.inputs.bias_step.value()
        series_header += '#\n# Files in Series:\n#\n'
        return series_fname, series_header

    def queue(self):
        direc = self.inputs.save_dir.text()
        # Make list of procedures
        procedures = self.make_procedures()
        if self.inputs.do_azimuth_sweep.isChecked() or \
           self.inputs.do_bias_sweep.isChecked():
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
            pre = procedure.sample_name + '_AMRField_P{polar:04.1f}_A{azimuth:04.1f}_DC{bias:04.1f}_'.format(polar=procedure.field_polar,
                                                                                                             azimuth=procedure.field_azimuth,
                                                                                                             bias=procedure.dc_bias)
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
                    There are no more queued AMR Field Sweep measurements on the Daedalus setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    Applied Voltage: {volt:g} V
                    DC Bias: {bias:g} A

                    Please update parameters or finish your measurement.
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        volt=experiment.procedure.applied_voltage,
                        bias=experiment.procedure.dc_bias
                        )
                    )
            elif not self.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    An AMR Field Sweep measurement has finished on the Daedalus setup. The
                    parameters of this scan were:

                    Sample Name: {name}
                    Azimuthal Angle: {azimuth:g} deg
                    Polar Angle: {polar:g} deg
                    Applied Voltage: {volt:g} V
                    DC Bias: {bias:g} A
                    """.format(
                        name=experiment.procedure.sample_name,
                        azimuth=experiment.procedure.field_azimuth,
                        polar=experiment.procedure.field_polar,
                        volt=experiment.procedure.applied_voltage,
                        bias=experiment.procedure.dc_bias
                        )
                    )
        if send_message:
            subject = '[AMR Field] Measurement finished on Daedalus Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusAMRFieldHystGUI()
    window.show()
    sys.exit(app.exec_())
