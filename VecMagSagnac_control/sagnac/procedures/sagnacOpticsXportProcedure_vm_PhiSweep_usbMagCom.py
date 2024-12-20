import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.instruments.zurich import HF2LI
from pymeasure.instruments.signalrecovery import DSP7265
from ..custom_instruments import vectorMagnetFullUSB
# from ..instruments.LTC20 import LTC20, change to our temperature controller

from pymeasure.instruments.keithley import Keithley6221
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
# from scanning import ANC150, ANC300
from time import sleep, time
import numpy as np
import atto_device.CRYO2100 as cr
from pymeasure.instruments.attocube import APS100

class sagnacOpticsXportProcedure_vm_PhiSweep_usbMagCom(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup and vector magnet using usb connection
    """
    print("azimuthal sweep class")
    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')
    attocube_device = cr("192.168.1.1")
    magnet = vectorMagnetFullUSB()
    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait time", units = 's', default =1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_phi_start = FloatParameter("Bias Magnetic Field Start Phi", units="deg", default=0)
    sweep_phi_end = FloatParameter("Bias Magnetic Field End Phi", units="deg", default=0)
    
    sweep_phi_step = FloatParameter("Bias Magnetic Field Phi step", units="deg", default=0)
    sweep_phi_field = FloatParameter("Bias Magnetic Field Magnitude", units="T", default=0.)
    sweep_phi_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)
    

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1) # current frequency 

    queued_time = Parameter('Time Queued')
    avgs = IntegerParameter("Number of Averages", default = 1)
   
    # voltage scans
    voltage_sweep = BooleanParameter("Apply voltage sweep?", default=False)
    voltage_start = FloatParameter("Applied Sample Voltage Start", units="V", default=0)
    voltage_stop = FloatParameter("Applied Sample Voltage End", units="V", default=0)
    voltage_step = FloatParameter("Applied Sample Voltage Step", units="V", default=0)
    voltage_scale_main = BooleanParameter("Apply 1V scale?", default=False)
    voltage_scale_sub = BooleanParameter("Apply 1V scale?", default=False)

    first = True
    last = True

    # need to change this
    DATA_COLUMNS = ["ThetaK", "X1","Y1","X2","Y2","DeltaThetaK", "DeltaThetaK_DualSideband","DeltaX1_C-M","DeltaY1_C-M", "DeltaX1_C+M", "DeltaY1_C+M", "TX1", "TY1", "TX2", "TY2", "sweep_phi","Bx","By","Bz", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")
        log.info("waiting for the wait time")
        sleep(self.wait)

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005, 1, 18338)

        #subscribe to outputs
        self.apply_bias_field = False
        if self.voltage_scale_main == False and self.voltage_scale_sub == False:
            self.lockin.set_vout(1, 6, self.applied_voltage/10*np.sqrt(2))
        else: 
            if self.applied_voltage <= 1 and self.applied_voltage >= -1:
                self.lockin.set_vout(1,6,self.applied_voltage*np.sqrt(2))
            else: 
                log.info("Warning: input voltage out of range (>1)! Divided by 10.")
                self.lockin.set_vout(1,6,self.applied_voltage/10*np.sqrt(2))

        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True

    def execute(self):
        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        if self.sweep_phi_start > self.sweep_phi_end and self.sweep_phi_step >0: 
            self.sweep_phi_step = -1 * self.sweep_phi_step
        phi_points = np.arange(self.sweep_phi_start,
                                 self.sweep_phi_end,
                                 self.sweep_phi_step)
        if self.sweep_phi_start not in phi_points:
            phi_points = np.append(phi_points,self.sweep_phi_start)

        if self.hysteresis:                        
            phi_points = np.append(phi_points, phi_points[::-1][1:])

        if self.reverse:
            phi_points = phi_points[::-1]
        
        if self.saturate:
            self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
            log.info("Setting saturation field")
            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 0.002):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break
            log.info("Set to saturation field")
        
        # self.device.magnet.setHSetPoint3D(0.0, 0.0, 0.0)
        self.magnet.set_field_cartesian(0, 0, 0)
        while (abs(self.device.magnet.getH(0)) > 0.002):
            sleep(0.5)
        log.info(f"Field set to 0 T")
        sleep(0.5)

        log.info("Waiting a while to equilibrate")
        sleep(self.wait)

        num_progress = phi_points.size
        start_time = time()

        for progress_iterator, phi in enumerate(phi_points):
            self.magnet.set_field_polar(self.sweep_phi_field,phi,self.sweep_phi_polar)
            log.info("waiting till field is set to setpoint")
            # sleep(0.1)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break
            # apply bias field
            while not self.magnet.check_field_polar(self.sweep_phi_field,phi,self.sweep_phi_polar, 0.002):
                sleep(0.5)
                self.magnet.set_field_polar(self.sweep_phi_field,phi,self.sweep_phi_polar)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break
            log.info("Recording results")

            rec_Bx,rec_By,rec_Bz = self.magnet.get_field_cartesian()
            log.info(f"Field set to {rec_Bx}, {rec_By}, {rec_Bz}")
            sleep(0.5)

            self.emit("progress", 100*progress_iterator/num_progress)
            self.lockin.sub(0)
            self.lockin.sub(1)
            self.lockin.sub(2)
            self.lockin.sub(3)
            self.lockin.sub(4)
            self.lockin.sub(5)
            try:
                sample_temp = self.attocube_device.sample.getTemperature()
            except:
                sample_temp = None
                
            vti_temp = self.attocube_device.vti.getTemperature()
            reservoir_temp = self.attocube_device.condenser.getTemperature()

            
            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync()
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,2,3,4,5], ['x','y'], ratio=False))
                log.info(self.lockin.poll_and_unpack(0.02, 100, [0,1,2,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}
            print("data_list: ", dat_list)
            self.lockin.unsubscribe("*")

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[2]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[2]['x'],
                "Y2": dat[2]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[2]['y']*2, #sideband signal is diminished by 1/2 relative to main carrier so *2 to get the actual signal,
                "DeltaThetaK_DualSideband": J2J1*(dat[4]['x'] + dat[5]['x'])/2/dat[2]['y'],
                "DeltaX1_C-M": dat[4]['x'],
                "DeltaY1_C-M": dat[4]['y'],
                "DeltaX1_C+M": dat[5]['x'],
                "DeltaY1_C+M": dat[5]['y'],
                "TX1": dat[0]['x'],
                "TY1": dat[0]['y'],
                "TX2": dat[1]['x'],
                "TY2": dat[1]['y'],
                "sweep_phi": phi,
                "Bx": rec_Bx,
                "By": rec_By,
                "Bz": rec_Bz,
                # "real_temperature": self.tempcontroller.sensor2_read_temp,
                "sample_temp": sample_temp,
                "vti_temp": vti_temp,
                "reservoir_temp": reservoir_temp,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        self.magnet.set_field_cartesian(0.0, 0.0, 0.0)
        while (abs(self.device.magnet.getH(0)) > 0.001):
            sleep(2)
        Bx, By, Bz = self.magnet.get_field_cartesian()
        self.magnet.shutdown()
        log.info(f"Field set to {Bx}, {By}, {Bz} T (this should be 0)")



