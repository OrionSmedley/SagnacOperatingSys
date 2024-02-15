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


class daedalusCenterCalibrationProcedure(Procedure):
    """
    Procedure for calibrating Daedalus. Calibrates X then Y. Moves to minimize
    the Z field using something like steepest descent, moving in a direction which
    should minimize the z field an amount which is proportional to the z field.
    Does so three times.
    """

    # control parameters
    calib_name = Parameter("Calibration Name", default='')

    mag_voltage = FloatParameter("Volts to magnet", units="V", default=5.)

    tolerance = FloatParameter("Field Tolerance", units='T', default=0.005)
    scaling = FloatParameter("Scaling from Z field difference to mm", units="mm/T", default=0.1)

    X_guess = FloatParameter("stage X guess", units="mm", default=12.)
    Y_guess = FloatParameter("stage Y guess", units="mm", default=13.)

    queued_time = Parameter("Queued Time")

    DATA_COLUMNS = ["X","Y","Xfield","Yfield","Zfield","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.motion_inst.x.position = self.X_guess
        self.magnet.motion_inst.y.position = self.Y_guess
        for err in self.magnet.errors:
            log.warning('%s'%err)
        log.info("Setting magnet voltage to %.2f V"%self.mag_voltage)
        self.magnet.volts = self.mag_voltage

        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev1', ['ai0','ai2','ai4']))

    def get_Bz(self):
        return -1*self.hall_probe.z_field

    def execute(self):
        start_time = time()
        self.magnet.motion_inst.phi.position = 0.
        while self.magnet.in_motion:
            sleep(0.05)
        sleep(.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        fz_current = self.get_Bz()
        besty = self.Y_guess
        oldy = besty + np.random.rand(1)[0]
        dy = besty - oldy
        bestx = self.X_guess
        oldx = bestx + np.random.rand(1)[0]
        dx = bestx - oldx

        # do three times to ensure we have converged on the correct one
        for _ in range(3):
            # find a good Y first
            while np.abs(fz_current) > self.tolerance:
                fz_old = fz_current
                fz_current = self.get_Bz()

                dy = -np.sign(besty - oldy)*np.sign(np.abs(fz_current) - np.abs(fz_old))*self.scaling*np.abs(fz_current)
                oldy = besty
                besty += dy

                self.magnet.motion_inst.y.position = besty
                # wait for all motion to finish
                while self.magnet.in_motion:
                    sleep(0.05)
                sleep(.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                self.emit('results',
                          {
                              "X": bestx,
                              "Y": besty,
                              "Xfield": self.hall_probe.x_field,
                              "Yfield": self.hall_probe.y_field,
                              "Zfield": self.get_Bz(),
                              "elapsed_time": time()-start_time
                          })
                if self.should_stop():
                    log.warning("Caught stop flag in procedure.")
                    break


            if not self.should_stop():
                self.magnet.motion_inst.y.position = besty
                self.magnet.motion_inst.phi.position = 90.
                while self.magnet.in_motion:
                    sleep(0.05)
                sleep(.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                fz_current = self.get_Bz()


                # find good X
                while np.abs(fz_current) > self.tolerance:
                    fz_old = fz_current
                    fz_current = self.get_Bz()

                    dx = np.sign(bestx - oldx)*np.sign(np.abs(fz_current) - np.abs(fz_old))*self.scaling*np.abs(fz_current)
                    oldx = bestx
                    bestx -= dx

                    self.magnet.motion_inst.x.position = bestx
                    # wait for all motion to finish
                    while self.magnet.in_motion:
                        sleep(0.05)
                    sleep(.1)
                    for err in self.magnet.errors:
                        log.warning('%s'%err)
                    self.emit('results',
                          {
                              "X": bestx,
                              "Y": besty,
                              "Xfield": self.hall_probe.x_field,
                              "Yfield": self.hall_probe.y_field,
                              "Zfield": self.get_Bz(),
                              "elapsed_time": time()-start_time
                          })
                    if self.should_stop():
                        log.warning("Caught stop flag in procedure.")
                        break
            if self.should_stop(): # to catch nested loops
                break

    def shutdown(self):
        log.info("Done with scan. Shutting down instruments")
        self.magnet.volts = 0

class daedalusCenterCalibrationGUI(ManagedWindow):
    def __init__(self):
        super().__init__(
            procedure_class=daedalusCenterCalibrationProcedure,
            displays=[
                'X_guess',
                'Y_guess',
                'tolerance',
                'scaling',
                'mag_voltage'
                ],
            x_axis='Y',
            y_axis='Zfield'
        )
        self.setWindowTitle('Daedalus Center Calibration GUI')

    def _setup_ui(self):
        """
        Loads custom QT UI for center calibration
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'center_calibration_gui.ui'))

    def make_procedure(self):
        procedure = daedalusCenterCalibrationProcedure()
        procedure.calib_name = self.inputs.calib_name.text()
        procedure.mag_voltage = self.inputs.mag_voltage.value()
        procedure.X_guess = self.inputs.X_guess.value()
        procedure.Y_guess = self.inputs.Y_guess.value()
        procedure.tolerance = self.inputs.tolerance.value()
        procedure.scaling = self.inputs.scaling.value()
        procedure.queued_time = strftime("%Y-%m-%d %H:%M:%S")

        return procedure

    def queue(self):
        fname = unique_filename(
            self.inputs.save_dir.text(),
            dated_folder=True,
            prefix=self.inputs.calib_name.text() + '_daedalus_center_calib_',
            suffix=''
        )
        procedure = self.make_procedure()
        results = Results(procedure, fname)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = daedalusCenterCalibrationGUI()
    window.show()
    sys.exit(app.exec_())
