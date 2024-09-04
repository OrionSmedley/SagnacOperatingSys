import logging

import PyQt5.QtCore
import PyQt5.QtWidgets
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
from sagnac.procedures import sagnacOpticsXportProcedure
import PyQt5
class sagnacOpticsXportGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['sweep_field', 'sweep_field_azimuth']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacOpticsXportGUI, self).__init__(
            procedure_class=sagnacOpticsXportProcedure,
            displays=[
                'sample_name',
                'current_frequency',
                'amp_gain',
                'sweep_field_start',
                'sweep_field_stop',
                'sweep_field_step',
                'sweep_field_azimuth',
                'saturating_field',
                'saturating_field_polar',
                'bias_field_x',
                'bias_field_y',
                'bias_field_z',
                'applied_voltage',
                'applied_voltage_offset','keithley_voltage'],
            x_axis='sweep_field',
            y_axis='ThetaK'
        )
        self.setWindowTitle('PyMeasure Sagnac Optics Xport Combo Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacOpticsXportGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/sagnac_gui_Heterodyne.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacOpticsXportProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        # procedure.current_amplitude = self.inputs.current_amplitude.value()/1e3
        procedure.applied_voltage = self.inputs.applied_voltage.value()
        procedure.applied_voltage_offset = self.inputs.applied_voltage_offset.value()

        procedure.use_keithley = self.inputs.use_keithley.isChecked()
        procedure.keithley_voltage = self.inputs.keithley_voltage.value()

        procedure.current_frequency = self.inputs.current_frequency.value()
        # procedure.current_offset = self.inputs.current_offset.value()/1e3
        procedure.amp_gain = self.inputs.amp_gain.value()
        procedure.settling = self.inputs.settling.value()
        procedure.wait = self.inputs.wait.value()
        procedure.avgs = self.inputs.avgs.value()

        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()

        procedure.hysteresis = self.inputs.hysteresis.isChecked()
        procedure.reverse = self.inputs.reverse.isChecked()
        procedure.sweep_field_start = self.inputs.sweep_field_start.value()
        procedure.sweep_field_stop = self.inputs.sweep_field_stop.value()
        procedure.sweep_field_step = self.inputs.sweep_field_step.value()
        procedure.sweep_field_azimuth = self.inputs.sweep_field_azimuth.value()
        procedure.sweep_field_polar = self.inputs.sweep_field_polar.value()

        procedure.bias_field_x = self.inputs.bias_field_x.value()
        procedure.bias_field_y = self.inputs.bias_field_y.value()
        procedure.bias_field_z = self.inputs.bias_field_z.value()

        procedure.input_range = self.inputs.input_range.value()
        procedure.imp50 = self.inputs.imp50.isChecked()

        procedure.f_eom = self.inputs.f_eom.value()*1e6

        procedure.first_harm_order = self.inputs.first_harm_order.value()
        procedure.second_harm_order = self.inputs.second_harm_order.value()
        procedure.first_harm_tc = self.inputs.first_harm_tc.value()
        procedure.second_harm_tc = self.inputs.second_harm_tc.value()

        procedure.eom_voltage = self.inputs.eom_voltage.value()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure
    
    def make_voltage_sweep(self, voltages):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """
        procedures = []
        for v in voltages:
            procedure = self.make_procedure()
            procedure.applied_voltage = v
            procedure.first = False
            procedure.last = False
            procedures.append(procedure)
        return procedures

    def make_4quadrant_sweep(self):
        """
        Makes a series of procedures varying bias field at a given bias field angle
        """

        procedures = []
        for satdir in [-1,1]:
            for fielddir in [-1,1]:
                procedure = self.make_procedure()

                procedure.sweep_field_start = 0
                procedure.sweep_field_stop = fielddir * self.inputs.sweep_field_stop.value()
                procedure.sweep_field_step = fielddir * self.inputs.sweep_field_step.value()

                procedure.saturating_field = satdir * self.inputs.saturating_field.value()

                procedure.direction = (satdir,fielddir)

                procedure.first = False
                procedure.last = False
                procedures.append(procedure)

         
        return procedures


    # def make_repeat_sweep(self, repeats):
    #     """
    #     Makes a series of the same procedure
    #     """
    #     procedures = []
    #     for i in range( int(repeats)):
    #         procedure = self.make_procedure()
    #         procedure.first = False #not sure what this is for
    #         procedure.last = False  #not sure what this is for
    #         procedures.append(procedure)
    #     return procedures

    def queue(self): #name of this one matters(according to what pymeaserure wants)
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        do_sweep = self.inputs.do_voltage_sweep.isChecked()
        # do_repeats = self.inputs.do_repeats.isChecked()
        do_fourQuadrant = self.inputs.do_fourQuadrant.isChecked()
        procedures = []
        for i in range( int(self.inputs.num_repeat.value())): 
            if do_sweep:
                voltages = np.arange(self.inputs.voltage_min.value(), 
                                    self.inputs.voltage_max.value(), 
                                    self.inputs.voltage_step.value())
                if self.inputs.voltage_max.value() not in voltages:
                    voltages = np.append(voltages,self.inputs.voltage_max.value())
                procedures += self.make_voltage_sweep(voltages)

            # elif do_repeats:
                # procedures = self.make_repeat_sweep(self.inputs.num_repeat.value())

            elif do_fourQuadrant:
                procedures += self.make_4quadrant_sweep()
            else:
                procedures += [self.make_procedure()]

        log.info(f"len(procedures) = {len(procedures)}")
        log.info("type(procedures) = {}".format(type(procedures)) )
        # procedure = procedures*2
        # log.info(f"len(procedures*2) = {len(procedures)}")
        pcount = 0 #procedure count

           
        for procedure in procedures:
            log.info("----------------------------------")
            log.info(f"pcount is {pcount}")
            pcount += 1
            log.info(f" for i={i}, at loop top, procedure.last is {procedure.last}")
            
            if procedure.sample_name == '':
                procedure.sample_name = 'test'

            if hasattr(procedure, "direction"):
                # log.info('Has direction attribute')
                direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + \
                    self.inputs.save_dir.text() + '\\' + \
                        'keith' + str(self.inputs.keithley_voltage.value())+ '\\' + \
                        'sat'+ str( procedure.direction[0])+ '\\' \
                        'field'+str(procedure.direction[1])
            else:
                # log.info('No direction attribute')
                pass
                    

            # create files
            pre = procedure.sample_name + \
                '_SagnacHeterodyne_V{current:0.1f}V_A{azimuth:0.1f}_Voff{offset:0.1f}V_Keith{keithleyV:0.1f}V_'.format(
                current=procedure.applied_voltage,
                azimuth=procedure.sweep_field_azimuth,
                offset=procedure.applied_voltage_offset,
                keithleyV=procedure.keithley_voltage
            )
            suf = ''
            filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                        prefix=pre)
            
            log.info(f" for i={i}, just before queing, procedure.last is {procedure.last}")
            # Queue experiment
            results = Results(procedure,filename)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)

    def finished(self, experiment): #name of this one matters(according to what pymeaserure wants)
        super().finished(experiment)

if __name__ == '__main__':
    app = PyQt5.QtWidgets.QApplication(sys.argv)
    window = sagnacOpticsXportGUI()
    window.show()
    sys.exit(app.exec_())
