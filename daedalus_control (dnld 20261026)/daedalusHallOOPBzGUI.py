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
from daedalus.procedures import HallOOPBzProcedure
from pymeasure.instruments.signalrecovery import DSP7265

from send_gmail import send_gmail

class daedalusHallOOPBzGUI(ManagedWindow):

    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super(daedalusHallOOPBzGUI, self).__init__(
            procedure_class=HallOOPBzProcedure,
            displays=[
                'sample_name',
                'field_strength_z_start',
                'field_strength_z_end',
                'field_strength_z_step',
                'lockin_voltage',
                'dc_bias'    
                ],
            x_axis='field_strength_z',
            y_axis='X'
        )
        self.setWindowTitle('PyMeasure HallOOPBz Field Scan')
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
        Loads custom QT UI for daedalus HallOOP measurements
        """
        super(daedalusHallOOPBzGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'custom_inputs/daedalus_gui_HallOOPBz.ui'))
        self.inputs.station_name.setText(self.system)
        self.inputs.calib_file.setText('./calibrations/' + self.system)

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = HallOOPBzProcedure()
        procedure.sample_name = self.inputs.sample_name.text()
        procedure.calib_file = self.inputs.calib_file.text()
        procedure.station_name = self.system

        procedure.field_strength_z_start = self.inputs.field_z_start.value()
        procedure.field_strength_z_end = self.inputs.field_z_end.value()
        procedure.field_strength_z_step = self.inputs.field_z_step.value()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms

        procedure.lockin_voltage = self.inputs.lockin_voltage.value()*1e-3 #mV
        procedure.sensitivity = DSP7265.SENSITIVITIES[self.inputs.sensitivity.currentIndex()]
        procedure.time_constant = DSP7265.TIME_CONSTANTS[self.inputs.time_constant.currentIndex()]

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


    def make_procedures(self):
        """
        Constructs a series of procedures based on gui options
        """
        procedures = []
        if self.inputs.do_bias_sweep.isChecked():
            procedures = self.make_dc_sweep()
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
        pre = sname + '_HallOOP_series_'
        suf = ''
        series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
                                       suffix=suf,dated_folder=True,ext='txt')
        series_header = '# swept procedure column: field_strength\n'

        if self.inputs.do_bias_sweep.isChecked():
            series_header += '# swept series parameter: dc_bias\n'
            series_header += '# Parameters:\n#\n'
            series_header += '# Initial DC bias: %g T\n'%self.inputs.bias_start.value()
            series_header += '# Final DC bias: %g T\n'%self.inputs.bias_end.value()
            series_header += '# DC bias step: %g T\n'%self.inputs.bias_step.value()

        series_header += '#\n# Files in Series:\n#\n'
        return series_fname, series_header

    def queue(self):
        direc = self.inputs.save_dir.text()
        # Make list of procedures
        procedures = self.make_procedures()
        if self.inputs.do_bias_sweep.isChecked():
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
            pre = procedure.sample_name + '_HallOOP_DC{bias:06.1f}_'.format(
                bias=procedure.dc_bias
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
                    There are no more queued HallOOP Sweep measurements on the {system} setup.
                    The last parameters ran were:

                    Sample Name: {name}
                    Lockin Voltage: {volt:g} V
                    DC Bias: {bias:g} A
                    Please update parameters or finish your measurement.
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        volt=experiment.procedure.lockin_voltage,
                        bias=experiment.procedure.dc_bias,
                        )
                    )
            elif not self.notify_at_end.isChecked():
                send_message = True
                message = textwrap.dedent("""\
                    An HallOOP Field Sweep measurement has finished on the {system} setup. The
                    parameters of this scan were:

                    Sample Name: {name}
                    Lockin Voltage: {volt:g} V
                    DC Bias: {bias:g} A
                    """.format(
                        system=self.system,
                        name=experiment.procedure.sample_name,
                        volt=experiment.procedure.lockin_voltage,
                        bias=experiment.procedure.dc_bias
                        )
                    )
        if send_message:
            subject = f'[HallOOP] Measurement finished on {self.system} Setup'
            addresses = [str(self.inputs.notify_email.text())]
            files = []
            if self.last_series_fname is not None: # attach sweep file if appropriate
                files.append(self.last_series_fname)
            send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)


if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = daedalusHallOOPBzGUI()
    window.show()
    sys.exit(app.exec_())
