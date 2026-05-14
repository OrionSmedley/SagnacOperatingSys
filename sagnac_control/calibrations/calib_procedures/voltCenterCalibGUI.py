# patch the old packages calling visa
# this is a hack to make the old packages work with pyvisa

#############################################################################################################################
import pyvisa

# Simulate the `visa` module as an alias for `pyvisa`
import sys

# Create a fake 'visa' module, which is essentially an alias for pyvisa
sys.modules['visa'] = pyvisa

# Optionally, map all attributes from pyvisa to visa (this is technically unnecessary because the alias works)
for attr in dir(pyvisa):
    setattr(sys.modules['visa'], attr, getattr(pyvisa, attr))

#############################################################################################################################

#############################################################################################################################

from PyQt5 import QtWidgets, QtGui

# Map all attributes from QtWidgets to QtGui without checking if they exist in QtGui
for attr in dir(QtWidgets):
    setattr(QtGui, attr, getattr(QtWidgets, attr))
#############################################################################################################################


import logging
import os
from time import sleep, time, strftime
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.experiment import FloatParameter, IntegerParameter, Parameter
from pymeasure.log import console_log
from pymeasure.experiment import Procedure
from pymeasure.adapters import DAQmxAdapter
from sagnac.custom_instruments import daedalusProjField, senis3AxHallProbe

from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
import sys
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi

class daedalusVoltCenterCalibrationProcedure(Procedure):
    """
    Procedure for calibrating the voltage to field strength relationship
    on Daedalus. Assumes that the center calibration has already ran.
    """

    # control parameters
    calib_name = Parameter("Calibration Name")

    magnet_phi = FloatParameter("Magnet Azimuthal Angle", units='deg', default=0.)

    voltage_start = FloatParameter("Start magnet voltage", units="V", default=-10.)
    voltage_stop = FloatParameter("Stop magnet voltage", units="V", default=10.)
    voltage_step = FloatParameter("Magnet voltage step", units="V", default=0.1)

    center_calib_name = Parameter("Center Calibration File")
    # calib_file = Parameter("Magnet Calibration Filename", default='./icarus')

    queued_time = Parameter("Queued Time")

    DATA_COLUMNS = ["V","Xfield","Yfield","Zfield","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        # self.x_zero, self.y_zero, self.z_zero = np.loadtxt(self.calib_file + '_hall_probe_zero_calib.csv', delimiter=',') #zero point of Hall probe calibrated using LakeShore Gaussmeter
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        centerX, centerY = np.loadtxt(self.center_calib_name, delimiter=',')
        log.info("Setting magnet position to X: {0}, Y: {1}".format(centerX, centerY))
        self.magnet.motion_inst.x.position = centerX
        self.magnet.motion_inst.y.position = centerY
        log.info("Setting magnet azimuthal position to phi: %f"%self.magnet_phi)
        self.magnet.motion_inst.phi.position = self.magnet_phi
        while self.magnet.in_motion:
            sleep(0.05)
        sleep(.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev1', ['ai0','ai2','ai4']))

    # def get_Bx_zeroed(self):
    #     return (self.hall_probe.x_field - self.x_zero)

    # def get_By_zeroed(self):
    #     return (self.hall_probe.y_field - self.y_zero)

    # def get_Bz_zeroed(self):
    #     return -1*(self.hall_probe.z_field - self.z_zero)

    def execute(self):
        start_time = time()

        voltage_points = np.arange(self.voltage_start, self.voltage_stop, self.voltage_step)
        if self.voltage_stop not in voltage_points:
            voltage_points = np.append(voltage_points, self.voltage_stop)

        voltage_points = np.concatenate((voltage_points, voltage_points[::-1]))

        num_progress = voltage_points.size

        for progress_iterator, v in enumerate(voltage_points):
            log.info("Setting magnet voltage to %f V"%v)
            self.magnet.volts = v
            sleep(0.02)
            self.emit('progress', int(100*progress_iterator/num_progress))
            self.emit('results',
                      {
                          "V": v,
                          "Xfield": self.hall_probe.x_field,
                          "Yfield": self.hall_probe.y_field,
                          "Zfield": self.hall_probe.z_field,
                          "elapsed_time": time()-start_time
                      })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Done with scan. Shutting down instruments")
        self.magnet.motion_inst.phi.position = 0.
        self.magnet.volts = 0

class daedalusVoltCenterCalibrationGUI(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=daedalusVoltCenterCalibrationProcedure,
            displays=[
                'calib_name',
                'voltage_start',
                'voltage_stop',
                'magnet_phi'
                ],
            x_axis='V',
            y_axis='Xfield'
        )
        self.setWindowTitle('Daedalus Volt Center Calibration GUI')

    def _setup_ui(self):
        """
        Loads custom QT UI for center calibration
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'voltCenter_calibration_gui.ui'))

    def make_procedure(self):
        procedure = daedalusVoltCenterCalibrationProcedure()
        procedure.calib_name = self.inputs.calib_name.text()
        procedure.voltage_start = self.inputs.voltage_start.value()
        procedure.voltage_stop = self.inputs.voltage_stop.value()
        procedure.voltage_step = self.inputs.voltage_step.value()
        procedure.center_calib_name = self.inputs.center_calib_name.text()
        procedure.magnet_phi = self.inputs.magnet_phi.value()
        procedure.queued_time = strftime("%Y-%m-%d %H:%M:%S")

        return procedure

    def queue(self):
        fname = unique_filename(
            self.inputs.save_dir.text(),
            dated_folder=True,
            prefix=self.inputs.calib_name.text() + '_daedalus_voltCenter_calib_',
            suffix=''
        )
        procedure = self.make_procedure()
        results = Results(procedure, fname)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = daedalusVoltCenterCalibrationGUI()
    window.show()
    sys.exit(app.exec_())
