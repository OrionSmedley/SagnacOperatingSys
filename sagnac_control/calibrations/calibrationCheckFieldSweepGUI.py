import logging
import os
from time import sleep
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
import socket
from pymeasure.experiment import FloatParameter, IntegerParameter, Parameter
from pymeasure.log import console_log
from pymeasure.experiment import Procedure
from pymeasure.adapters import DAQmxAdapter
from daedalus.custom_instruments import daedalusProjField, senis3AxHallProbe

from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
import sys
from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from itertools import product


class icarusCalibCheckFieldSweepProcedure(Procedure):
    """
    Procedure for making a raser image of the field components of Daedalus
    """

    # control parameters
    name = Parameter("Calibration Name", default='')
    mag_field = FloatParameter("Magnetic field strength", units="T", default=0.05)
    num_averages = IntegerParameter("Number of Averages", default=1)
    delay = FloatParameter("Delay between averages", units="s", default=.1)
    phi_start = FloatParameter("Phi Start Position", units="mm", default=10.)
    phi_end = FloatParameter("Phi End Position", units="mm", default=13.)
    phi_step = FloatParameter("Phi Scan Step Size", units="mm", default=0.1)
    theta_start = FloatParameter("Theta Start Position", units="mm", default=10.)
    theta_end = FloatParameter("Theta End Position", units="mm", default=13.)
    theta_step = FloatParameter("Theta Scan Step Size", units="mm", default=0.1)
    calib_file = Parameter("Magnet Calibration Filename", default='./calibrations')
    station_name = Parameter("Probe Station Name", default='')

    first = True
    last = True

    DATA_COLUMNS = ["phi","theta","X", "Y", "act_phi", "act_theta", "Xfield_avg","Yfield_avg","Zfield_avg","Xfield_std",
                    "Yfield_std","Zfield_std", "Bmag", "Bmag_deviation", "Bmag_percent_dev", "V", "act_V"  ]

    def startup(self):
        log.info("Using calibration file: " + self.calib_file + " on station: " + self.station_name)
        log.info("Connecting and configuring the instruments")
        self.hall_probe = senis3AxHallProbe(DAQmxAdapter('Dev2', ['ai0','ai2','ai4']))
        self.magnet = daedalusProjField(DAQmxAdapter('Dev2', ['ao0', 'ai1']),"GPIB::10")
        for err in self.magnet.errors:
        	log.warning('%s' % err)
        self.magnet.load_calibration_params(self.calib_file)
        self.x_zero, self.y_zero, self.z_zero = np.loadtxt(self.calib_file + '_hall_probe_zero_calib.csv', delimiter=',')
        #zero point of Hall probe calibrated using LakeShore Gaussmeter
        log.info("Setting magnet field to %.2f T"%self.mag_field)
        log.info("Setting magnet position to Phi: {0}, Theta: {1}".format(self.phi_start, self.theta_start))
        self.magnet.set_vector_field(self.mag_field, self.phi_start, self.theta_start)
        while self.magnet.in_motion:
            sleep(0.05)
        sleep(.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

    def get_Bx_zeroed(self):
        return (self.hall_probe.x_field - self.x_zero)

    def get_By_zeroed(self):
        return (self.hall_probe.y_field - self.y_zero)

    def get_Bz_zeroed(self):
        return -1*(self.hall_probe.z_field - self.z_zero)

    def execute(self):
        phis = np.arange(self.phi_start, self.phi_end + self.phi_step, self.phi_step)
        thetas = np.arange(self.theta_start, self.theta_end + self.theta_step, self.theta_step)

        num_progress = float(phis.size * thetas.size) * self.num_averages
        progress_iterator = 0
        self.emit('progress',int(100*progress_iterator/num_progress))

        for theta in thetas:
            for phi in phis:
                log.info("moving magnet to Phi: %g deg, Theta: %g deg"%(phi, theta))
                self.magnet.set_vector_field(self.mag_field, phi, theta)
                # wait for all motion to finish
                while self.magnet.in_motion:
                    sleep(0.05)
                errors = self.magnet.errors
                for err in errors:
                    log.warning('%s'%err)

                x = self.magnet.motion_inst.x.position
                y = self.magnet.motion_inst.y.position
                v = self.magnet.getVolts()

                xfields = np.array([])
                yfields = np.array([])
                zfields = np.array([])
                for j in range(self.num_averages):
                    sleep(self.delay)
                    log.info("Recording average %d of %d"%(j+1,self.num_averages))
                    progress_iterator += 1
                    self.emit('progress',int(100*progress_iterator/num_progress))
                    xfields = np.append(xfields,self.get_Bx_zeroed())
                    yfields = np.append(yfields,self.get_By_zeroed())
                    zfields = np.append(zfields,self.get_Bz_zeroed())
                
                Bmag = np.sqrt(np.mean(xfields)**2 + np.mean(yfields)**2 + np.mean(zfields)**2)

                self.emit("results", {
                "phi": phi,
                "theta": theta,
                "X":x,
                "Y":y,
                "act_phi": np.arctan2(np.mean(xfields),np.mean(yfields))*180/np.pi,
                "act_theta": np.arctan2(np.mean(zfields), np.sqrt(np.mean(yfields)**2 + np.mean(xfields)**2))*180/np.pi,
                "Xfield_avg": np.mean(xfields),
                "Xfield_std": np.std(xfields),
                "Yfield_avg": np.mean(yfields),
                "Yfield_std": np.std(yfields),
                "Zfield_avg": np.mean(zfields),
                "Zfield_std": np.std(zfields),
                "Bmag": Bmag,
                "Bmag_deviation": Bmag - self.mag_field, 
                "Bmag_percent_dev": (Bmag - self.mag_field)/Bmag*100,
                "V" : self.magnet.set_volts,  
                "act_V" : v
                })
                if self.should_stop():
                    log.warning("Caught stop flag in procedure")
                    break # out of x steps
            else: # to catch nested loops
                continue
            break # out of y steps


    def shutdown(self):
        log.info("Done with image scan. Shutting down instruments")
        self.magnet.voltage = 0.

class icarusCalibCheckFieldSweepGUI(ManagedWindow):
        SWEEP_PARAM_NAMES = ['field']
        NUM_SWEEP_PARAMS = len(SWEEP_PARAM_NAMES)

        def __init__(self):
            super().__init__(
                procedure_class=icarusCalibCheckFieldSweepProcedure,
                displays=[
                    'mag_field',
                    'num_averages',
                    'phi_start',
                    'phi_end',
                    'theta_start',
                    'theta_end'
                    ],
                x_axis='theta',
                y_axis='Bmag_percent_dev'
                #z_axis='Xfield_avg'
            )
            self.setWindowTitle('Icarus Calib Check FieldSweep GUI')

        def identifySystem(self):
                hostname = socket.gethostname()
                return hostname

        def _setup_ui(self):
            """
            Loads custom QT UI
            """
            super()._setup_ui()
            self.inputs.hide()
            self.run_directory = os.path.dirname(os.path.realpath(__file__))
            self.inputs = fromUi(os.path.join(self.run_directory,'custom_inputs/calibrationCheckFieldSweep_gui.ui'))
            self.inputs.station_name.setText(self.identifySystem())
            self.inputs.calib_file.setText('./calibrations/' + self.identifySystem().lower())

        def make_procedure(self):
            procedure = icarusCalibCheckFieldSweepProcedure()
            procedure.name = self.inputs.name.text()
            procedure.mag_field = self.inputs.mag_field.value()
            procedure.num_averages = self.inputs.num_averages.value()
            procedure.delay = self.inputs.delay.value()
            procedure.calib_file = self.inputs.calib_file.text()
            procedure.station_name = self.identifySystem()

            procedure.phi_start = self.inputs.phi_start.value()
            procedure.phi_end = self.inputs.phi_end.value()
            procedure.phi_step = self.inputs.phi_step.value()
            procedure.theta_start = self.inputs.theta_start.value()
            procedure.theta_end = self.inputs.theta_end.value()
            procedure.theta_step = self.inputs.theta_step.value()

            return procedure

        def make_procedures(self, fields):
                """
                Makes a series of procedures varying fields
                """
                procedures = []
                for field in fields:
                    procedure = self.make_procedure()
                    procedure.mag_field = field
                    procedure.first = False
                    procedure.last = False
                    procedures.append(procedure)
                return procedures

        def queue(self):
                do_sweep = self.inputs.do_sweeps.isChecked()
                direc = self.inputs.save_dir.text()

                if do_sweep: 
                    fields = np.arange(self.inputs.mag_field.value(), self.inputs.field_end.value(), self.inputs.field_step.value())
                    if self.inputs.field_end.value() not in fields: # ensure we capture the endpoint
                        fields= np.append(fields,self.inputs.field_end.value())
                    # create list of procedures to run
                    procedures = self.make_procedures(fields)

                else:
                    procedures = [self.make_procedure()]

                for procedure in procedures:
                    # ensure *some* sample name exists so Results.load() works

                    # create files
                    pre = procedure.name + '_calibCheck_F{field:.3f}_'.format(
                        field=procedure.mag_field,
                    )
                    suf = ''
                    filename = unique_filename(direc,dated_folder=True,suffix=suf,
                                               prefix=pre)

                    # Queue experiment
                    results = Results(procedure,filename)
                    experiment = self.new_experiment(results)
                    self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = icarusCalibCheckFieldSweepGUI()
    window.show()
    sys.exit(app.exec_())
