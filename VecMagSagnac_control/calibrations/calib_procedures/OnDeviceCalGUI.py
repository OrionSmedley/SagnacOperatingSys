import logging
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
from sagnac.procedures import sagnacHeterodyneProcedure

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.zurich import HF2LI
from sagnac.custom_instruments import daedalusProjField
from pymeasure.instruments.keithley import Keithley6221
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
import numpy as np

class sagnacOnDevCalProcedure(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    magnet_voltage = FloatParameter("Magnet Voltage", units="V", default=1)
    magnet_phi = FloatParameter("Magnet azimuthal angle", units="deg", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)
    queued_time = Parameter('Time Queued')

    X_start = FloatParameter("stage X Start Position", units="mm", default=10.)
    X_end = FloatParameter("stage X End Position", units="mm", default=13.)
    X_step = FloatParameter("stage X Scan Step Size", units="mm", default=0.1)
    Y_start = FloatParameter("stage Y Start Position", units="mm", default=10.)
    Y_end = FloatParameter("stage Y End Position", units="mm", default=13.)
    Y_step = FloatParameter("stage Y Scan Step Size", units="mm", default=0.1)

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","x","y","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        log.info("Connecting to the magnet")
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)


        #subscribe to outputs
        # self.lockin.sub(0)
        # self.lockin.sub(1)
        # self.lockin.sub(2)
        self.lockin.sub(3)
        # self.lockin.sub(4)
        self.lockin.sub(5)

    def execute(self):
        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        xs = np.arange(self.X_start, self.X_end + self.X_step, self.X_step)
        ys = np.arange(self.Y_start, self.Y_end + self.Y_step, self.Y_step)

        num_progress = float(xs.size * ys.size)
        progress_iterator = 0
        self.emit('progress',int(100*progress_iterator/num_progress))
        
        if self.saturate:
            # ensure we have gotten to the phi we want
            while not np.isclose(self.magnet.phi, self.saturating_field_azimuth, atol=1e-3):
                log.info(f"setting magnet azimuthal orientation to {self.saturating_field_azimuth} deg")
                self.magnet.phi = self.saturating_field_azimuth
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
            # NOTE: in the future will probably want to check that we have actually reached
            # the theta value we set it to.
            log.info(f"setting magnet polar orientation to {self.saturating_field_polar} degrees")
            self.magnet.theta = self.saturating_field_polar
            nom_x, _, _ = self.magnet.angle_calibration(self.saturating_field_polar, self.saturating_field_azimuth) #temporary fix for bad x axis
            att = 1
            while not np.isclose(self.magnet.motion_inst.x.position, nom_x, atol=1e-3): #temporary fix for bad x axis
                self.magnet.motion_inst.x.enable()
                self.magnet.motion_inst.x.position = nom_x
                sleep(0.1)
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                att = att + 1
                log.info(f"attempt number {att}")
                
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            log.info("Setting the Saturating Field")
            self.magnet.set_vector_field(self.saturating_field,
                                         phi=self.saturating_field_azimuth, 
                                         theta=self.saturating_field_polar)
            log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")
            sleep(self.settling)

            self.magnet.volts = 0
        
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.magnet_phi, atol=1e-3):
            log.info(f"setting magnet azimuthal orientation to {self.magnet_phi} deg")
            self.magnet.phi = self.magnet_phi
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)


        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        log.info("Waiting a while to equilibrate")
        sleep(self.settling*5)

        start_time = time()

        for y in ys:
            for x in xs:
                log.info("moving magnet to X: %g mm, Y: %g mm"%(x, y))
                self.magnet.motion_inst.x.position = x
                self.magnet.motion_inst.y.position = y
                progress_iterator += 1
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                self.emit("progress", 100*progress_iterator/num_progress)
               
                self.magnet.volts = self.magnet_voltage
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                dat = self.lockin.poll_and_unpack(self.settling, 100, [3,5], ['x','y'], ratio=False)
   
                self.emit('results', {
                    "ThetaK": np.arctan(J2J1*(dat[3]['x']/dat[5]['y']))/2,
                    "X1": dat[3]['x'],
                    "Y1": dat[3]['y'],
                    "X2": dat[5]['x'],
                    "Y2": dat[5]['y'],
                    "x": x,
                    "y": y,
                    "elapsed_time": time()-start_time})
                if self.should_stop():
                    log.warning("Caught stop flag in procedure.")
                    break
            else: # to catch nested loops
                continue
            break # out of y steps

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            # self.magnet.shutdown()
            self.magnet.volts = 0
            # if self.apply_current:
            #     self.source.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)


class sagnacOnDevCalGUI(ManagedWindow):

    SWEEP_PARAM_NAMES = ['x', 'y']
    NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

    def __init__(self):
        super(sagnacOnDevCalGUI, self).__init__(
            procedure_class=sagnacOnDevCalProcedure,
            displays=[
                'sample_name',],
            x_axis='x',
            y_axis='ThetaK'
        )
        self.setWindowTitle('PyMeasure On Device Calibration Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for Sagnac DC Hysteresis measurements
        """
        super(sagnacOnDevCalGUI, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'sagnac_gui_OnDevCal.ui'))
        self.inputs.save_dir.setText("junk")

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = sagnacOnDevCalProcedure()
        procedure.sample_name = self.inputs.sample_name.text()

        procedure.magnet_voltage = self.inputs.magnet_voltage.value()
        procedure.magnet_phi = self.inputs.magnet_phi.value()
        procedure.settling = self.inputs.settling.value()

        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()
        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        procedure.X_start = self.inputs.x_start.value()
        procedure.X_end = self.inputs.x_end.value()
        procedure.X_step = self.inputs.x_step.value()
        procedure.Y_start = self.inputs.y_start.value()
        procedure.Y_end = self.inputs.y_end.value()
        procedure.Y_step = self.inputs.y_step.value()

        return procedure
    

    def queue(self):
        direc = 'C:\\Users\\Ralph Group\\Documents\\Data\\' + self.inputs.save_dir.text()
        procedure = self.make_procedure()
        if procedure.sample_name == '':
            procedure.sample_name = 'test'

        # create files
        pre = procedure.sample_name + \
            '_SagnacOnDevCal_V{current:0.4f}V_A{azimuth:0.1f}_'.format(
            current=procedure.magnet_voltage,
            azimuth=procedure.magnet_phi,
        )
        suf = ''
        filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                    prefix=pre)
        # Queue experiment
        results = Results(procedure,filename)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

    def finished(self, experiment):
        super().finished(experiment)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = sagnacOnDevCalGUI()
    window.show()
    sys.exit(app.exec_())
