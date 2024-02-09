import logging
import os
from time import sleep
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.experiment import FloatParameter, IntegerParameter, Parameter
from pymeasure.log import console_log
from pymeasure.experiment import Procedure
from pymeasure.adapters import DAQmxAdapter
from sagnac.custom_instruments import daedalusProjField, senis3AxHallProbe

from pymeasure.display.windows import ManagedImageWindow
from pymeasure.experiment import Results, unique_filename
import sys
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi


class daedalusFieldRasterProcedure(Procedure):
    """
    Procedure for making a raser image of the field components of Daedalus
    """

    # control parameters
    name = Parameter("name", default='')

    mag_voltage = FloatParameter("Volts to magnet", units="V", default=5.)
    num_averages = IntegerParameter("Number of Averages", default=1)
    delay = FloatParameter("Delay between averages", units="s", default=.1)
    phi = FloatParameter("Magnet Phi", units='deg', default=0.)

    X_start = FloatParameter("stage X Start Position", units="mm", default=10.)
    X_end = FloatParameter("stage X End Position", units="mm", default=13.)
    X_step = FloatParameter("stage X Scan Step Size", units="mm", default=0.1)
    Y_start = FloatParameter("stage Y Start Position", units="mm", default=10.)
    Y_end = FloatParameter("stage Y End Position", units="mm", default=13.)
    Y_step = FloatParameter("stage Y Scan Step Size", units="mm", default=0.1)
    # calib_file = Parameter("Magnet Calibration Filename", default='./icarus')


    DATA_COLUMNS = ["X","Y","Xfield_avg","Yfield_avg","Zfield_avg","Xfield_std",
                    "Yfield_std","Zfield_std"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        # self.x_zero, self.y_zero, self.z_zero = np.loadtxt(self.calib_file + '_hall_probe_zero_calib.csv', delimiter=',')
        # log.info("x zero: %.3f, y zero: %.3f, z_zero: %.3f" % (self.x_zero, self.y_zero, self.z_zero))
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        log.info("setting magnet phi to %.1f degrees"%self.phi)
        self.magnet.motion_inst.phi.position = self.phi
        log.info("Setting magnet voltage to %.2f V"%self.mag_voltage)
        self.magnet.volts = self.mag_voltage

        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev1', ['ai0','ai2','ai4']))

    # def get_Bx_zeroed(self):
    #     return (self.hall_probe.x_field - self.x_zero)

    # def get_By_zeroed(self):
    #     return (self.hall_probe.y_field - self.y_zero)

    # def get_Bz_zeroed(self):
    #     return -1*(self.hall_probe.z_field - self.z_zero)

    def execute(self):
        xs = np.arange(self.X_start, self.X_end + self.X_step, self.X_step)
        ys = np.arange(self.Y_start, self.Y_end + self.Y_step, self.Y_step)

        num_progress = float(xs.size * ys.size) * self.num_averages
        progress_iterator = 0
        self.emit('progress',int(100*progress_iterator/num_progress))

        for y in ys:
            for x in xs:
                log.info("moving magnet to X: %g mm, Y: %g mm"%(x, y))
                self.magnet.motion_inst.x.position = x
                self.magnet.motion_inst.y.position = y
                # wait for all motion to finish
                while self.magnet.in_motion:
                    sleep(0.05)
                errors = self.magnet.errors
                for err in errors:
                    log.warning('%s'%err)
                xfields = np.array([])
                yfields = np.array([])
                zfields = np.array([])
                for j in range(self.num_averages):
                    sleep(self.delay)
                    log.info("Recording average %d of %d"%(j+1,self.num_averages))
                    progress_iterator += 1
                    self.emit('progress',int(100*progress_iterator/num_progress))
                    xfields = np.append(xfields,self.hall_probe.x_field)
                    yfields = np.append(yfields,self.hall_probe.y_field)
                    zfields = np.append(zfields,self.hall_probe.z_field)
                self.emit("results", {
                "X": x,
                "Y": y,
                "Xfield_avg": np.mean(xfields),
                "Xfield_std": np.std(xfields),
                "Yfield_avg": np.mean(yfields),
                "Yfield_std": np.std(yfields),
                "Zfield_avg": np.mean(zfields),
                "Zfield_std": np.std(zfields)
                })
                if self.should_stop():
                    log.warning("Caught stop flag in procedure")
                    break # out of x steps
            else: # to catch nested loops
                continue
            break # out of y steps


    def shutdown(self):
        log.info("Done with image scan. Shutting down instruments")
        self.magnet.volts = 0.

class daedalusFieldRasterGUI(ManagedImageWindow):
        def __init__(self):
            super().__init__(
                procedure_class=daedalusFieldRasterProcedure,
                displays=[
                    'mag_voltage',
                    'num_averages',
                    'X_start',
                    'X_end',
                    'Y_start',
                    'Y_end'
                    ],
                x_axis='X',
                y_axis='Y',
                z_axis='Xfield_avg'
            )
            self.setWindowTitle('Daedalus Field Raster GUI')

        def _setup_ui(self):
            """
            Loads custom QT UI
            """
            super()._setup_ui()
            self.inputs.hide()
            self.run_directory = os.path.dirname(os.path.realpath(__file__))
            self.inputs = fromUi(os.path.join(self.run_directory,'fieldRaster_gui.ui'))

        def make_procedure(self):
            procedure = daedalusFieldRasterProcedure()

            procedure.name = self.inputs.name.text()

            procedure.mag_voltage = self.inputs.mag_voltage.value()
            procedure.num_averages = self.inputs.num_averages.value()
            procedure.delay = self.inputs.delay.value()
            procedure.phi = self.inputs.phi.value()

            procedure.X_start = self.inputs.X_start.value()
            procedure.X_end = self.inputs.X_end.value()
            procedure.X_step = self.inputs.X_step.value()
            procedure.Y_start = self.inputs.Y_start.value()
            procedure.Y_end = self.inputs.Y_end.value()
            procedure.Y_step = self.inputs.Y_step.value()

            return procedure

        def queue(self):
            fname = unique_filename(
                self.inputs.save_dir.text(),
                dated_folder=True,
                prefix=self.inputs.name.text() + '_fieldRaster_',
                suffix=''
            )
            procedure = self.make_procedure()
            results = Results(procedure, fname)
            experiment = self.new_experiment(results)
            self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = daedalusFieldRasterGUI()
    window.show()
    sys.exit(app.exec_())
