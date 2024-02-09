import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from ..custom_instruments import daedalusProjField
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
from pymeasure.instruments.keithley import Keithley2400
import numpy as np

class AMRKeithleyProcedure(Procedure):
    """
    Procedure for taking PHE Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    applied_field = FloatParameter("Applied Magnetic Field", units="T", default=0.1)
    field_azimuth_start = FloatParameter("Field Azimuth start", units="deg", default=0)
    field_azimuth_end = FloatParameter("Field Azimuth stop", units="deg", default=170)
    field_azimuth_step = FloatParameter("Field Azimuth step", units="deg", default=1)
    field_polar = FloatParameter("Field Polar", units="deg", default=0)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["R","field_azimuth","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        log.info("Connecting to the magnet")
        self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        self.magnet.load_calibration_params(self.calib_file)

        log.info("Connecting to the Keithley")
        self.Keithley = Keithley2400(4)

    def execute(self):
        deg2rad = np.pi/180.
        angles = np.arange(self.field_azimuth_start,
                           self.field_azimuth_end,
                           self.field_azimuth_step)
        if self.field_azimuth_end not in angles:
            angles = np.append(angles,self.field_azimuth_end)
        
        self.magnet.phi = self.field_azimuth_start
        # ensure we have gotten to the phi we want
        while not np.isclose(self.magnet.phi, self.field_azimuth_start, atol=1e-3):
            log.info(f"setting magnet azimuthal orientation to {self.field_azimuth_start} deg")
            self.magnet.phi = self.field_azimuth_start
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
        # NOTE: in the future will probably want to check that we have actually reached
        # the theta value we set it to.
        log.info(f"setting magnet polar orientation to {self.field_polar} degrees")
        self.magnet.theta = self.field_polar
        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)
        log.info("Setting Field")
        self.magnet.field = self.applied_field
        log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")

        while self.magnet.in_motion: # wait for all motion to finish
            sleep(0.1)
        for err in self.magnet.errors:
            log.warning('%s'%err)

        num_progress = angles.size
        start_time = time()

        for progress_iterator, ang in enumerate(angles):
            self.emit("progress", 100*progress_iterator/num_progress)
            self.magnet.phi = ang
            log.info(f"Setting Magnetic azimuth to {ang:.1f} deg")
            while self.magnet.in_motion: # wait for all motion to finish
                sleep(0.1)
            for err in self.magnet.errors:
                log.warning('%s'%err)
            
            log.info("Recording results")

            sleep(1)

            self.emit('results', {
                "R": self.Keithley.resistance,
                "field_azimuth": ang,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            # self.magnet.shutdown()
            self.magnet.volts = 0
            #self.lockin.shutdown()
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)