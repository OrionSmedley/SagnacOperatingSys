import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
import socket
import numpy as np

from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename

VOLTAGE_RANGES = [10e-3, 100e-3, 1, 10, 100]
FILTER_TYPES = ['repeating', 'moving']
WINDOW_HEIGHTS = [0, 0.01, 0.1, 1., 10.]

from daedalus.custom_instruments import daedalusProjFieldYokogawa, Keithley2182A, DSP7265
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter

from time import sleep, time

class HallSweepNanovoltmeter(Procedure):
    """
    Procedure for taking out-of-plane Hall Measurements with the Daedalus setup
    """

    
    sample_name = Parameter("Sample Name", default='')
    station = Parameter("Station", default='daedalus')
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    sweep_field_start = FloatParameter("Magnetic Field Start", units="T", default=0.1)
    sweep_field_stop = FloatParameter("Magnetic Field Stop", units="T", default=0.1)
    sweep_field_step = FloatParameter("Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Magnetic Field Polar", units="deg", default=0.0)

    delay = FloatParameter("Delay", units="s", default=0.5)

    applied_current = FloatParameter("Applied Current", units='A', default=1e-3)

    nvolt_range = FloatParameter("Nanovoltmeter Range", units="V", default=0.01)
    nvolt_rate = FloatParameter("Nanovoltmeter Measurement Rate", units="NPLC", default=1.0)
    nvolt_analog_filter = BooleanParameter("Nanovoltmeter Use Analog Filter?", default=False)
    nvolt_digital_filter = BooleanParameter("Nanovoltmeter Use Digital Filter?", default=False)
    nvolt_n_dfilt = IntegerParameter("Nanovoltmeter Digital Filter Averages", default=5)
    nvolt_dfilt_type = Parameter("Nanovoltmeter Digital Filter Type", default='repeating')
    nvolt_diflt_window = FloatParameter("Nanovoltmeter Digital Filter Window", default=0)

    queued_time = Parameter('Time Queued')
    
    first = True
    last = True

    DATA_COLUMNS = ["field_strength","Vxx","Vxy","up1_dn0_indicator","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        self.magnet = daedalusProjFieldYokogawa("GPIB::2","GPIB::10")
        for err in self.magnet.errors:
            log.warning('%s'%err)
        self.magnet.load_calibration_params(self.calib_file)

        self.voltmeter = Keithley2182A("GPIB::8")
        if not self.voltmeter.calibration_is_good():
            log.warning("Nanovoltmeter calibration is not good! It should be redone")
        self.voltmeter.set_voltage_mode()
        self.voltmeter.channel = 1
        if self.nvolt_analog_filter:
            self.voltmeter.enable_low_pass_filter()
        else:
            self.voltmeter.disable_low_pass_filter()
        if self.nvolt_digital_filter:
            self.voltmeter.configure_digital_filter(self.nvolt_diflt_window, self.nvolt_n_dfilt, self.nvolt_dfilt_type)
        else:
            self.voltmeter.disable_digital_filter()
        self.voltmeter.rate = self.nvolt_rate
        self.voltmeter.voltage_range = self.nvolt_range

        self.sourcemeter = Keithley2400("GPIB::4")
        self.sourcemeter.apply_current(current_range=self.applied_current*1.05,compliance_voltage=0.1)
        self.sourcemeter.measure_voltage(voltage=2.1, auto_range=False)
        self.sourcemeter.source_current = self.applied_current
        self.sourcemeter.enable_source()
        
    def execute(self):
        
        # Set up field points
        step_direction = np.sign(self.sweep_field_stop-self.sweep_field_start)
        field_points = np.arange(self.sweep_field_start,
                                 self.sweep_field_stop,
                                 step_direction*self.sweep_field_step)
        if self.sweep_field_stop not in field_points:
            field_points = np.append(field_points,self.sweep_field_stop)

        if step_direction < 0:
            ud_indicator = np.zeros_like(field_points)
        else:
            ud_indicator = np.ones_like(field_points)

        if self.hysteresis:                        
            field_points = np.append(field_points, field_points[::-1])
            ud_indicator = np.append(ud_indicator, 1-ud_indicator)
        
        # Saturate the field if requested
        if self.saturate:
            while not np.isclose(self.magnet.phi, self.saturating_field_azimuth, atol=1e-3):
                log.info(f"setting magnet azimuthal orientation to {self.saturating_field_azimuth} deg")
                self.magnet.phi = self.saturating_field_azimuth
                while self.magnet.in_motion:
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
                    
            log.info(f"setting magnet polar orientation to {self.saturating_field_polar} degrees")
            self.magnet.theta = self.saturating_field_polar
            while self.magnet.in_motion:
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            log.info("Setting the Saturating Field")
            self.magnet.set_vector_field(self.saturating_field,
                                         phi=self.saturating_field_azimuth, 
                                         theta=self.saturating_field_polar)
            log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")
            sleep(2)

            self.magnet.volts = 0
        
        # Go to sweep position
        while not np.isclose(self.magnet.phi, self.sweep_field_azimuth, atol=1e-3):
                log.info(f"setting magnet azimuthal orientation to {self.sweep_field_azimuth} deg")
                self.magnet.phi = self.sweep_field_azimuth
                while self.magnet.in_motion: # wait for all motion to finish
                    sleep(0.1)
                for err in self.magnet.errors:
                    log.warning('%s'%err)
        log.info(f"setting magnet polar orientation to {self.sweep_field_polar} degrees")
        self.magnet.theta = self.sweep_field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        log.info("Setting Sweep Field")
        self.magnet.field = field_points[0]
        log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")


        # Run the desired scan
        num_progress = field_points.size
        start_time = time()
        
        for progress_iterator, (B, ud) in enumerate(zip(field_points, ud_indicator)):
            self.emit("progress", int(100*progress_iterator/num_progress))
            log.info("Setting magnetic field to %g T" % B)
            self.magnet.field = B
            sleep(self.delay)
            
            log.info("Recording results")
            self.emit('results', {
                "field_strength": B,
                "Vxx": self.sourcemeter.voltage,
                "Vxy": self.voltmeter.voltage,
                "up1_dn0_indicator": ud,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.magnet.volts = 0
            self.sourcemeter.disable_source()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)
                      
class HallSweepNanovoltmeterGUI(ManagedWindow):
    
    def __init__(self):
        super().__init__(
            procedure_class=HallSweepNanovoltmeter,
            displays=[
                'sample_name',
                'sweep_field_azimuth',
                'sweep_field_polar',
                'sweep_field_start',
                'sweep_field_stop',
                'applied_current',
                'hysteresis',
                'saturate',
                'saturating_field',
                'saturating_field_polar',
                ],
            x_axis='field_strength',
            y_axis='Vxy'
        )
        self.setWindowTitle('PyMeasure Hall Field Scan Nanovoltmeter')
        self.last_series_fname = None
        
            
    def _setup_ui(self):
        hname = socket.gethostname().lower()
        if hname == 'icarus':
            self.system = 'icarus'
        elif hname == 'cheezburger':
            self.system = 'daedalus'
        else:
            self.system = 'unknown'
        super()._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,'hall_nanovoltmeter_gui.ui'))
        self.inputs.station_name.setText(self.system)
        self.inputs.calib_file.setText('C:\\Users\\RalphGroup\\Documents\\group_code\\daedalus_control\\calibrations\\' + self.system)

    def make_procedure(self):
        """
        Constructs a single procedure
        """
        procedure = HallSweepNanovoltmeter()
        procedure.sample_name = self.inputs.sample_name.text()
        procedure.station = self.system
        procedure.calib_file = self.inputs.calib_file.text()
        
        procedure.saturate = self.inputs.saturate.isChecked()
        procedure.saturating_field = self.inputs.saturating_field.value()
        procedure.saturating_field_azimuth = self.inputs.saturating_field_azimuth.value()
        procedure.saturating_field_polar = self.inputs.saturating_field_polar.value()
        
        procedure.hysteresis = self.inputs.hysteresis.isChecked()
        procedure.sweep_field_start = self.inputs.sweep_field_start.value()
        procedure.sweep_field_stop = self.inputs.sweep_field_stop.value()
        procedure.sweep_field_step = self.inputs.sweep_field_step.value()
        procedure.sweep_field_azimuth = self.inputs.sweep_field_azimuth.value()
        procedure.sweep_field_polar = self.inputs.sweep_field_polar.value()
        
        procedure.delay = self.inputs.delay.value()
        procedure.applied_current = self.inputs.applied_current.value()/1e3
        
        procedure.nvolt_range = VOLTAGE_RANGES[self.inputs.voltage_range.currentIndex()]
        procedure.nvolt_rate = self.inputs.nvolt_rate.value()
        procedure.nvolt_analog_filter = self.inputs.analog_filter.isChecked()
        procedure.nvolt_digital_filter = self.inputs.digital_filter.isChecked()
        procedure.nvolt_n_dfilt = self.inputs.dfilt_averages.value()
        procedure.nvolt_dfilt_type = FILTER_TYPES[self.inputs.dfilt_type.currentIndex()]
        procedure.nvolt_diflt_window = WINDOW_HEIGHTS[self.inputs.dfilt_window.currentIndex()]

        procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

        return procedure
    
    def queue(self):
        direc = self.inputs.save_dir.text()
        procedure = self.make_procedure()
        if procedure.sample_name == '':
            procedure.sample_name = 'undefined'
        
        pre = f"{procedure.sample_name}_I{procedure.applied_current:0.4f}_A{procedure.sweep_field_azimuth:0.1f}_P{procedure.sweep_field_polar:0.1f}_HallNanovoltmeter_"
        suf = ''
        filename = unique_filename(direc, dated_folder=True, suffix=suf, prefix=pre)
        results = Results(procedure, filename)
        experiment = self.new_experiment(results)
        self.manager.queue(experiment)
        
    def finished(self, experiment):
        super().finished(experiment)
        
if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = HallSweepNanovoltmeterGUI()
    window.show()
    sys.exit(app.exec_())