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

class daedalusRadialPoloarCalibrationProcedure(Procedure):
    """
    Procedure for calibrating the radial distance / polar angle relationship
    on Daedalus. Only moves along Y with phi=0. Assumes that the center
    calibration was already ran.
    """

    # control parameters
    calib_name = Parameter("Calibration Name")

    magnet_voltage = FloatParameter("Magnet Voltage", units='V', default=0.)
    magnet_phi = FloatParameter("Azimuthal Angle", units='deg', default=0.)

    r_start = FloatParameter("Start Y position", units="mm", default=-10.)
    r_stop = FloatParameter("Stop Y position", units="mm", default=10.)
    r_step = FloatParameter("Y position step", units="mm", default=0.1)

    center_calib_name = Parameter("Center Calibration File")

    queued_time = Parameter("Queued Time")

    DATA_COLUMNS = ["R","Xfield","Yfield","Zfield","theta", "phi", "B", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        # self.x_zero, self.y_zero, self.z_zero = 0.0437063, 0.0434812, 0.0437816 #zero point of Hall probe calibrated using LakeShore Gaussmeter
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        self.centerX, self.centerY = np.loadtxt(self.center_calib_name, delimiter=',')
        log.info("Setting magnet position to X: {0}, Y: {1}".format(self.centerX, self.centerY))
        log.info("Setting magnet azimuthal orientation to %g deg"%self.magnet_phi)
        self.magnet.motion_inst.x.position = self.centerX
        self.magnet.motion_inst.y.position = self.centerY
        self.magnet.motion_inst.phi.position = self.magnet_phi
        log.info("Setting magnet voltage to %f V"%self.magnet_voltage)
        self.magnet.volts = self.magnet_voltage
        while self.magnet.in_motion:
            sleep(0.2)
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

        r_points = np.arange(self.r_start, self.r_stop, self.r_step)
        if self.r_stop not in r_points:
            r_points = np.append(r_points, self.r_stop)

        num_progress = r_points.size

        for progress_iterator, r in enumerate(r_points):
            log.info("Azimuthal angle is %g"%self.magnet_phi)
            xloc = -1*r*np.sin(self.magnet_phi*np.pi/180.) + self.centerX
            yloc = r*np.cos(self.magnet_phi*np.pi/180.) + self.centerY
            log.info("Setting magnet to radial distance %f mm from center"%r)
            log.info("Setting magnet to position X: {0} mm, Y: {1} mm".format(xloc, yloc))
            self.magnet.motion_inst.y.position = yloc
            self.magnet.motion_inst.x.position = xloc
            while self.magnet.in_motion:
                sleep(0.05)
            sleep(.2) # to wait for motion to really stop
            self.emit('progress', int(100*progress_iterator/num_progress))
            xfield = self.hall_probe.x_field
            yfield = self.hall_probe.y_field
            zfield = self.hall_probe.z_field
            inplanefield = np.sqrt(xfield**2 + yfield**2)
            theta = np.arctan2(zfield, inplanefield)*180/np.pi
            phi = np.arctan2(xfield, yfield)*180/np.pi
            B = np.sqrt(xfield**2+yfield**2+zfield**2)

            self.emit('results',
                      {
                          "R": r,
                          "Xfield": self.hall_probe.x_field,
                          "Yfield": self.hall_probe.y_field,
                          "Zfield": self.hall_probe.z_field,
                          "theta": theta,
                          "phi": phi,
                          "B": B,
                          "elapsed_time": time()-start_time
                      })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Done with scan. Shutting down instruments")
        self.magnet.motion_inst.phi.position = 0.
        self.magnet.motion_inst.x.position = self.centerX
        self.magnet.motion_inst.y.position = self.centerY
        self.magnet.volts = 0

class daedalusRadialPolarCalibrationGUI(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=daedalusRadialPoloarCalibrationProcedure,
            displays=[
                'calib_name',
                'r_start',
                'r_stop',
                'magnet_voltage'
                ],
            x_axis='R',
            y_axis='Zfield'
        )
        self.setWindowTitle('Daedalus Radial Polar Calibration GUI')

    def _setup_ui(self):
        """
        Loads custom QT UI for center calibration
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'radialPolar_calibration_gui.ui'))

    def make_procedure(self):
        procedure = daedalusRadialPoloarCalibrationProcedure()
        procedure.calib_name = self.inputs.calib_name.text()
        procedure.r_start = self.inputs.r_start.value()
        procedure.r_stop = self.inputs.r_stop.value()
        procedure.r_step = self.inputs.r_step.value()
        procedure.center_calib_name = self.inputs.center_calib_name.text()
        procedure.magnet_voltage = self.inputs.magnet_voltage.value()
        procedure.magnet_phi = self.inputs.magnet_phi.value()
        procedure.queued_time = strftime("%Y-%m-%d %H:%M:%S")

        return procedure

    def queue(self):
        fname = unique_filename(
            self.inputs.save_dir.text(),
            dated_folder=True,
            prefix=self.inputs.calib_name.text() + '_daedalus_radialPolar_calib_A%05.1f_'%self.inputs.magnet_phi.value(),
            suffix=''
        )
        procedure = self.make_procedure()
        results = Results(procedure, fname)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = daedalusRadialPolarCalibrationGUI()
    window.show()
    sys.exit(app.exec_())
