import logging
import os
import socket
from datetime import datetime
from time import sleep, time, strftime
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.experiment import FloatParameter, IntegerParameter, Parameter
from pymeasure.log import console_log
from pymeasure.experiment import Procedure
# from pymeasure.adapters import DAQmxAdapter
from daedalus.custom_instruments import daedalusProjFieldYokogawa, Keithley220, DAQmxAdapter, DSP7265, daedalusProjFieldDAQ, senis3AxHallProbe

from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
import sys
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi


class daedalusRotationCalibrationProcedure(Procedure):
    """
    Procedure for calibrating Daedalus. Calibrates X then Y. Moves to minimize
    the Z field using something like steepest descent, moving in a direction which
    should minimize the z field an amount which is proportional to the z field.
    Does so three times.
    """

    # control parameters
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')
    sample_name = Parameter("Sample Name", default='')
    num_averages = IntegerParameter("Number of Averages", default=1)
    
    field_strength = FloatParameter("Field Strength", units="T", default=0.0)
    field_polar = FloatParameter("Magnetic Field Polar Angle", units="deg", default=0.)
    field_azimuth_start = FloatParameter("Start Azimuthal Field", units="deg", default=0.)
    field_azimuth_end = FloatParameter("End Azimuthal Field", units="deg", default=0.1)
    field_azimuth_step = FloatParameter("Azimuthal Field Step", units="deg", default=0.05)

    queued_time = Parameter("Queued Time")

    DATA_COLUMNS = ["field_azimuth", "Xfield_avg","Yfield_avg","Zfield_avg","Xfield_std",
                    "Yfield_std","Zfield_std", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjFieldDAQ(DAQmxAdapter("Dev1", ['ao0', 'ai4']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        
        log.info(f"setting magnet azimuthal orientation to {self.field_azimuth_start} degrees")
        self.magnet.phi = self.field_azimuth_start
        voltage_pole_elim = np.sign(self.field_strength) * 10
        log.info(f"Setting magnet voltage to {voltage_pole_elim} V to eliminate pole remnants")
        self.magnet.volts = voltage_pole_elim
        log.info(f"setting magnet field strength to {self.field_strength} T")
        self.magnet.field = self.field_strength

        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev1', ['ai2','ai0','ai1']))

    def execute(self):
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end, self.field_azimuth_step)
        if self.field_azimuth_end not in angles: # ensure we have the last one
            angles = np.append(angles,self.field_azimuth_end)

        num_progress = angles.size
        start_time = time()
        sleep(5)

        for progress_iterator, angle in enumerate(angles):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info(f"Setting azimuthal field angle to {angle} deg")
            self.magnet.phi = angle
            for err in self.magnet.errors:
                log.warning('%s'%err)
            while self.magnet.in_motion:
                sleep(0.1)
            sleep(self.delay)
            log.info("Recording results")
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
            self.emit('results', {
                "field_azimuth": angle,
                "Xfield_avg": np.mean(xfields),
                "Xfield_std": np.std(xfields),
                "Yfield_avg": np.mean(yfields),
                "Yfield_std": np.std(yfields),
                "Zfield_avg": np.mean(zfields),
                "Zfield_std": np.std(zfields),
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Done with scan. Shutting down instruments")
        self.magnet.volts = 0

class daedalusRotationCalibrationGUI(ManagedWindow):
    def __init__(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super().__init__(
            procedure_class=daedalusRotationCalibrationProcedure,
            displays=[
                'sample_name',
                'field_azimuth_start',
                'field_azimuth_end',
                'field_azimuth_step',
                'field_strength'
                ],
            x_axis='field_azimuth',
            y_axis='Xfield_avg'
        )
        self.setWindowTitle('PyMeasure Calibration Azimuth Scan')
        self.last_series_fname = None

    def _setup_ui(self):
        """
        Loads custom QT UI for daedalus AMR measurements
        """
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'rotation_calibration_gui.ui'))
        self.inputs.station_name.setText(self.system)
        if self.system == 'icarus':
            self.inputs.save_dir.setText("C:\\Users\\TopMob\\Data\\junk")
            self.inputs.azimuth_start.setValue(-170.)
            self.inputs.azimuth_end.maximum.setValue(170.)
        elif self.system == 'daedalus':
            self.inputs.save_dir.setText("F:\\junk")
            self.inputs.azimuth_start.setValue(0.)
            self.inputs.azimuth_end.setValue(360.)
        self.inputs.calib_file.setText('C:/Users/RalphGroup/Documents/group_code/daedalus_control/calibrations/' + self.system)

    def make_procedure(self):
        procedure = daedalusRotationCalibrationProcedure()
        procedure.calib_file = self.inputs.calib_file.text()
        procedure.field_azimuth_start = self.inputs.azimuth_start.value()
        procedure.field_azimuth_end = self.inputs.azimuth_end.value()
        procedure.field_azimuth_step = self.inputs.azimuth_step.value()
        procedure.field_polar = self.inputs.polar_field.value()
        procedure.field_strength = self.inputs.field_start.value()
        procedure.delay = self.inputs.delay.value()*1e-3 # ms
        procedure.sample_name = self.inputs.sample_name.text()
        procedure.station_name = self.system
        procedure.queued_time = strftime("%Y-%m-%d %H:%M:%S")

        return procedure

    def queue(self):
        fname = unique_filename(
            self.inputs.save_dir.text(),
            dated_folder=True,
            prefix='daedalus_rotation_calib_',
            suffix=''
        )
        procedure = self.make_procedure()
        results = Results(procedure, fname)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = daedalusRotationCalibrationGUI()
    window.show()
    sys.exit(app.exec_())
