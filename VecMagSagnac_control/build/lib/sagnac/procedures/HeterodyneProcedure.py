import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.instruments.zurich import HF2LI
from pymeasure.instruments.signalrecovery import DSP7265
from ..custom_instruments import vectorMagnetBase, vectorMagnetX, vectorMagnetY, vectorMagnetZ, vectorMagnetFull
# from ..instruments.LTC20 import LTC20, change to our temperature controller

from pymeasure.instruments.keithley import Keithley6221
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
# from scanning import ANC150, ANC300
from time import sleep, time
import numpy as np
import atto_device.CRYO2100 as cr

class sagnacHeterodyneProcedure_vm(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup and vector magnet
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')
    device = cr("192.168.1.1")
    # device.connect()
    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait time", units = 's', default =1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_field_min = FloatParameter("Minimum Sweep Magnetic Field", units="T", default=0.1)
    sweep_field_max = FloatParameter("Maximum Sweep Magnetic Field", units="T", default=0.1)
    sweep_field_step = FloatParameter("Bias Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    # temp_setpoint = FloatParameter("temperature Setpoint", units="K", default=5.)

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK", "X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","sweep_field","Bx","By","Bz", "real_temperature","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        log.info("Connecting and configuring temperature controller")
        self.tempcontroller = LTC20("GPIB::19")
        print("LTC20: Connection established")
        log.info("LTC20: Connection established")
        self.tempcontroller.lock() #Disabling front panel until LOCAL key is pressed
        #sleep(setup_delay)
        print("LTC20: Locked front panel")
        log.info("LTC20: Locked front panel")
        #sleep(setup_delay)


        print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        self.magnet = vectorMagnetFull(self.device) #X,Y,Z in that order
        # self.magnet = self.device.magnet
        log.info("Connecting to the Zurich Lock-in")
        # self.lockin = HF2LI(8005,1,1004)
        self.lockin = HF2LI(8005, 1, 18338)

        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True

    def execute(self):
        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        field_points = np.arange(self.sweep_field_min,
                                 self.sweep_field_max,
                                 self.sweep_field_step)
        log.info("waiting for the wait time")
        sleep(self.wait) 
        if self.sweep_field_min not in field_points:
            field_points = np.append(field_points,self.sweep_field_min)
        
        #field_points = field_points[::-1]

        #field_points = np.append(field_points,
        #                        -1*field_points[::-1][1:])
        if self.hysteresis:                        
            field_points = np.append(field_points, field_points[::-1][1:])

        if self.reverse:
            field_points = field_points[::-1]
        
        if self.saturate:
            self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
            log.info("Setting saturation field")
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

        #Checking magnet's status to ensure that it successfully reaches the
        #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
          
        num_progress = field_points.size
        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)

            self.device.magnet.set_field_polar(field,self.sweep_field_azimuth,self.sweep_field_polar)
            log.info("waiting till field is set to setpoint")
            sleep(0.1)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break

            while self.magnet.is_ramping():
                sleep(2)
                log.info("Magnet is ramping")
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(field,self.sweep_field_azimuth,self.sweep_field_polar, 5e-3):
                sleep(0.1)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            #Checking magnet's status to ensure that it successfully reaches the
            #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)

            if self.magnet.is_holding():
                log.info("Field set to %g T, %g deg, %g deg and magnet status is HOLDING" % (field,self.sweep_field_azimuth,self.sweep_field_polar))
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
                break
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break

            # sleep(self.field_sweep_delay)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break
            log.info("Recording results")

            rec_Bx,rec_By,rec_Bz = self.magnet.get_field_cartesian()
            sleep(0.5)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break
          

            # if progress_iterator == 0: # only triggers before taking the first data point
            #     log.info("waiting for the wait time")
            #     sleep(self.wait) 
            

            self.lockin.sync() # clears buffer since field has changed
            sleep(self.settling)
            self.lockin.sync()
            dat = self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False)
            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y']*2, #sideband signal is diminished by 1/2 relative to main carrier so *2 to get the actual signal,
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "sweep_field": field,
                "Bx": rec_Bx,
                "By": rec_By,
                "Bz": rec_Bz,
                "real_temperature": self.tempcontroller.sensor1_read_temp,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break



    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            # self.magnet.shutdown()
           # self.magnet.volts = 0
            # if self.apply_current:
            #     self.source.shutdown()
            self.magnet.shutdown()


            while self.magnet.is_ramping():
                sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
                    #checking the status for every 22 Gauss change

            Bx, By, Bz = self.magnet.get_field_cartesian()
            if self.magnet.is_holding() and np.isclose(Bx,0,atol=5e-3) and np.isclose(By,0, atol=5e-3) and np.isclose(Bz,0,atol=5e-3):
                log.info("%s" %self.status)
                log.info("Field set to 0T. Finished shutting down")
            else:
                log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")
                #self.magnet.set_zero()

                self.tempcontroller.shutdown()
                self.lockin1.shutdown()
                log.info("Lockin: voltage not set to zero in shutdown procedure")
        else:
            log.info("Finished with one scan, but more to go.")
            sleep(1)

class sagnacHeterodyneProcedure_vm_highZ(Procedure):

    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup and using vector magnet for sweeping high Z field
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_current = FloatParameter("Applied Sample current", units="A", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    # current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait time", units = 's', default =1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_field = FloatParameter("Magnetic Field", units="T", default=0.1)
    sweep_field_start = FloatParameter("Magnetic Field Start", units="T", default=0.)
    sweep_field_step = FloatParameter("Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')


    # temp_setpoint = FloatParameter("temperature Setpoint", units="K", default=5.)

    first = True
    last = True

    #DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","sweep_field","Bz", "elapsed_time"]
    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","sweep_field","Bz", "real_temperature", "elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        # log.info("Keithley2400 current ramped to %g uA", self.applied_current)
        print("Setting up Z magnet")
        log.info("Setting up Z magnet")
        self.magnet = vectorMagnetZ("GPIB::24") #Connecting to Z
        log.info("Connection with magnet established")

        log.info("waiting for the wait time")
        sleep(self.wait) 
      
          # Connecting to Keithley 2400
        # self.keithley1 = Keithley2400("GPIB::29") 
        # self.keithley1.enable_source() 
        # log.info("Ramping Keithly to %g A", self.applied_current)
        # self.keithley1.ramp_to_current(self.applied_current)
        # print(self.keithley1.current[1])
        # while not np.isclose(self.keithley1.current[1],self.applied_current, rtol=5e-1):
        #     print(self.keithley1.current[1])
        #     sleep(1)
        #     if self.should_stop():
        #         log.info("Caught stop flag in procedure.")
        #         break
            
        log.info("Connecting and configuring temperature controller")
        self.tempcontroller = LTC20("GPIB::19")
        print("LTC20: Connection established")
        log.info("LTC20: Connection established")
        self.tempcontroller.lock() #Disabling front panel until LOCAL key is pressed
        print("LTC20: Locked front panel")
        log.info("LTC20: Locked front panel")

        log.info("Connecting to the Zurich Lock-in")
        # http://127.0.0.1:8006/1
        self.lockin = HF2LI("127.0.0.1:8006")
        # connect to our lockin: 
        # self.lockin = 

        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True
        # Note: this is just the port resource
        self.stepper = ANC150("COM3")
        # self.stepper.set_f(self.x_axis, 1000)
        # self.stepper.set_v(self.x_axis, 35)
        if self.x_enable:
            log.info("X enabled")
            self.stepper.set_mode(self.x_axis, 'stp')
        # self.stepper.set_f(self.y_axis, 1000)
        # self.stepper.set_v(self.y_axis, 32)
        if self.y_enable:
            log.info("y enabled")
            self.stepper.set_mode(self.y_axis, 'stp')

    def execute(self):
        if self.x_enable:
            log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
            if self.delta_x >= 0:
                self.stepper.stepu(1, self.delta_x)
            else:
                self.stepper.stepd(1, -self.delta_x)
        if self.y_enable:
            log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
            if self.delta_y >= 0:
                self.stepper.stepu(2, self.delta_y)
            else:
                self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        field_points = np.arange(self.sweep_field_start,
                                 self.sweep_field,
                                 self.sweep_field_step)
        if self.sweep_field not in field_points:
            field_points = np.append(field_points,self.sweep_field)
        
        # field_points = field_points[::-1]

        # field_points = np.append(field_points,
        #                          -1*field_points[::-1])

        if self.reverse:
            field_points = field_points[::-1]
        if self.hysteresis:                        
            # field_points = np.append(field_points, field_points[::-1][1:])
            field_points = np.append(field_points, field_points[::-1])
        
        # if self.saturate:
        #     self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
        #     log.info("Setting saturation field")
        #     while self.magnet.is_ramping():
        #         sleep(2)
        #         if self.should_stop():
        #             log.info("Caught stop flag in procedure.")
        #             break

        #     while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
        #         sleep(0.5)
        #         if self.should_stop():
        #             log.info("Caught stop flag in procedure.")
        #             break

        #Checking magnet's status to ensure that it successfully reaches the
        #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)

            # if self.magnet.is_holding():
            #     log.info(" magnet status is HOLDING" )
            # elif self.magnet.is_zeroing() or self.magnet.is_quenched():
            #     log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
            #     raise ValueError('Quench detected. Aborting procedures!')
            # elif self.should_stop():
            #     log.info("Caught stop flag in procedure.")
            # else:
            #     log.warning("Could not reach setpoint. Exiting procedures and aborting")
           
        num_progress = field_points.size
        start_time = time()
        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info("Setting field to %g T" % field)
            self.magnet.field = field
            log.info("waiting till field is set to setpoint")
            sleep(0.1)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break

            while self.magnet.is_ramping():
                sleep(2)
                log.info("Magnet is ramping")
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not np.isclose(field, self.magnet.field, atol = 5e-5):
                # log.info(f'{self.magnet.field - field}')
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            #Checking magnet's status to ensure that it successfully reaches the
            #setpoint without quenching or zeroing
           
            if self.magnet.is_holding():
                log.info("Field set to %g T magnet status is HOLDING" % (field))
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
                break
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break

            rec_Bz = self.magnet.field
            sleep(0.5)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break

            # if progress_iterator == 0: # only triggers before taking the first data point
            #     log.info("waiting for the wait time")
            #     sleep(self.wait) 
            
            self.lockin.sync() # clears buffer since field has changed
            sleep(self.settling)
            self.lockin.sync()
            dat = self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False)
            log.info("Recording results")
            self.emit('results', {
                 
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[2]['y'])/2, # mode 4 (1st harmonic) / mode 3(second harmonic)
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[2]['x'],
                "Y2": dat[2]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y']*2, #sideband signal is diminished by 1/2 relative to main carrier so *2 to get the actual signal,
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "sweep_field": field,
                "Bz": rec_Bz,
                'real_temperature':self.tempcontroller.sensor1_read_temp,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        # if self.last or self.should_stop():
        log.info("Finished with scans. Shutting down instruments.")
        self.magnet.shutdown()
        while self.magnet.is_ramping():
            sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
                #checking the status for every 22 Gauss change

        Bz= self.magnet.field
        if self.magnet.is_holding() and np.isclose(Bz,0,atol=5e-3):
            log.info("%s" %self.status)
            log.info("Field set to 0T. Finished shutting down")
        else:
            log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")
            #self.magnet.set_zero()
            self.tempcontroller.shutdown()
        # self.lockin1.shutdown()
        self.stepper.shut_down()

class sagnacHeterodyneProcedure_vm_PhiSweep(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup and vector magnet
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')
    device = cr("192.168.1.1")
    # applied_current = FsloatParameter("Applied Sample DC Current", units="A", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    #current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    
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
    # imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1) # current frequency 

    queued_time = Parameter('Time Queued')
    avgs = IntegerParameter("Number of Averages", default = 1)
    # temp_setpoint = FloatParameter("temperature Setpoint", units="K", default=5.)
    # voltage scans
    voltage_sweep = BooleanParameter("Apply voltage sweep?", default=False)
    voltage_start = FloatParameter("Applied Sample Voltage Start", units="V", default=0)
    voltage_stop = FloatParameter("Applied Sample Voltage End", units="V", default=0)
    voltage_step = FloatParameter("Applied Sample Voltage Step", units="V", default=0)
    voltage_scale_main = BooleanParameter("Apply 1V scale?", default=False)
    voltage_scale_sub = BooleanParameter("Apply 1V scale?", default=False)

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK", "X1","Y1","X2","Y2","DeltaThetaK", "DeltaThetaK_DualSideband","DeltaX1_C-M","DeltaY1_C-M", "DeltaX1_C+M", "DeltaY1_C+M", "TX1", "TY1", "TX2", "TY2", "sweep_phi","Bx","By","Bz", "elapsed_time"]
    magnet = vectorMagnetFull(device)

    def startup(self):
        log.info("Connecting and configuring the instruments")

        # log.info("Connecting and configuring temperature controller")
        # self.tempcontroller = LTC20("GPIB::20")
        # print("LTC20: Connection established")
        # log.info("LTC20: Connection established")
        # self.tempcontroller.lock() #Disabling front panel until LOCAL key is pressed
        # sleep(setup_delay)
        # print("LTC20: Locked front panel")
        # log.info("LTC20: Locked front panel")
        # sleep(setup_delay)

        log.info("waiting for the wait time")
        sleep(self.wait)
        # log.info("Connecting to the magnet")
        # self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
        # self.magnet.load_calibration_params(self.calib_file)

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
        
        # phi_points = phi_points[::-1]

        # phi_points = np.append(phi_points,
                                #  -1*phi_points[::-1][1:])
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

        #Checking magnet's status to ensure that it successfully reaches the
        #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)
        
        self.device.magnet.setHSetPoint3D(0.0, 0.0, 0.0)
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

            #Checking magnet's status to ensure that it successfully reaches the
            #setpoint without quenching or zeroing
            # sleep(self.field_sweep_delay)

            # if self.magnet.is_holding():
            #     log.info("Field set to %g T, %g deg, %g deg and magnet status is HOLDING" % (self.sweep_phi_field,phi,self.sweep_phi_polar))
            # elif self.magnet.is_zeroing() or self.magnet.is_quenched():
            #     log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
            #     raise ValueError('Quench detected. Aborting procedures!')
            # else:
            #     log.warning("Could not reach setpoint. Exiting procedures and aborting")
            #     break
            # if self.should_stop():
            #     log.info("Caught stop flag in procedure.")
            #     break

            # sleep(self.field_sweep_delay)
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

            # if self.should_stop():
            #     log.info("Caught stop flag in procedure.")
            #     break
          
            # if progress_iterator == 0: # only triggers before taking the first data point
            #     log.info("waiting for the wait time")
            #     sleep(self.wait) 
            
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
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break



    def shutdown(self):
        # if self.last or self.should_stop():
        log.info("Finished with scans. Shutting down instruments.")
        # self.magnet.shutdown()
        # self.magnet.volts = 0
        # if self.apply_current:
        #     self.source.shutdown()
        self.device.magnet.setHSetPoint3D(0.0, 0.0, 0.0)

        while (abs(self.device.magnet.getH(0)) > 0.001):
            sleep(2)

        Bx, By, Bz = self.magnet.get_field_cartesian()
        log.info(f"Field set to {Bx}, {By}, {Bz} T (this should be 0)")
        # else:
            # log.info("Finished with one scan, but more to go.")
            # sleep(1)

class sagnacOpticsXportProcedure_vm(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')
    device = cr("192.168.1.1")
    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=0)
    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_field_start = FloatParameter("Bias Magnetic Field start", units="T", default=0.1)
    sweep_field_stop = FloatParameter("Bias Magnetic Field stop", units="T", default=0.1)
    sweep_field_step = FloatParameter("Bias Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    # for voltage sweep stuff
    voltage_sweep = BooleanParameter("Apply voltage sweep?", default=False)
    voltage_start = FloatParameter("Applied Sample Voltage Start", units="V", default=0)
    voltage_stop = FloatParameter("Applied Sample Voltage End", units="V", default=0)
    voltage_step = FloatParameter("Applied Sample Voltage Step", units="V", default=0)
    voltage_scale_main = BooleanParameter("Apply 1V scale?", default=False)
    voltage_scale_sub = BooleanParameter("Apply 1V scale?", default=False)
    # if (self.voltage_start > self.voltage_stop) and (self.voltage_step > 0):
    #     voltage_step = -1 * voltage_step
    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaThetaK_DualSideband", "DeltaX1_C-M", "DeltaY1_C-M", "DeltaX1_C+M", "DeltaY1_C+M","TX1","TY1","TX2","TY2","sweep_field","elapsed_time"]

    magnet = vectorMagnetFull(device) #X,Y,Z in that order
    def startup(self):
        log.info("Connecting and configuring the instruments")

        # print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        # self.z_magnet = vectorMagnetZ("GPIB::24")

        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005, 1, 18338)
        # if self.voltage_sweep == False:
        if self.voltage_scale_main == False and self.voltage_scale_sub == False: 
            self.lockin.set_vout(1,6,self.applied_voltage/10*np.sqrt(2)) #using output 7
        else: 
            if self.applied_voltage <= 1 and self.applied_voltage >= -1:
                self.lockin.set_vout(1,6,self.applied_voltage*np.sqrt(2))
            else: 
                log.info("Warning: input voltage out of range (>1)! Divided by 10.")
                self.lockin.set_vout(1,6,self.applied_voltage/10*np.sqrt(2))
        log.info(f"set voltage to {self.lockin.get_vout(1, 6)/np.sqrt(2)}")
        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True

    def execute(self):
        
        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.

        if self.sweep_field_start>self.sweep_field_stop and self.sweep_field_step>0:
            self.sweep_field_step= -1 * self.sweep_field_step
        field_points = np.arange(self.sweep_field_start,
                                self.sweep_field_stop,
                                self.sweep_field_step)
        if self.sweep_field_stop not in field_points:
            field_points = np.append(field_points,self.sweep_field_stop)
            

            # log.info(f"field ")
        
        
        if self.hysteresis:                        
            field_points = np.append(field_points, field_points[::-1][1:])
            # voltage_points = np.append(voltage_points, voltage_points[::-1][1:])

        if self.reverse:
            field_points = field_points[::-1]
        
        if self.saturate:
            self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)
            log.info("Setting saturation field")
            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 0.002):
                sleep(0.5)
            log.info("Saturation field set")
        
        self.device.magnet.setHSetPoint3D(0.0, 0.0, 0.0)
        while (abs(self.device.magnet.getH(0)) > 0.002):
            sleep(0.5)
        log.info(f"Field set to 0 T")
        sleep(0.5)

        log.info("Waiting a while to equilibrate")
        sleep(self.wait)

        num_progress = field_points.size
        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            # specify which direction
            # set cap to 1T
            # log.info(f"how many iterations: {len(field_points)}")
            # log.info(f"set voltage to {self.lockin.get_vout(1, 6)}")
            # if self.voltage_sweep == True:
            #     self.lockin.set_vout(1,6,field/10*np.sqrt(2))
            # else: 
            if self.apply_bias_field:
                Bx = field*np.cos(np.deg2rad(self.sweep_field_azimuth))*np.sin(np.deg2rad(self.sweep_field_polar)) + self.bias_field_x
                By = field*np.sin(np.deg2rad(self.sweep_field_azimuth))*np.sin(np.deg2rad(self.sweep_field_polar)) + self.bias_field_y
                Bz = field*np.cos(np.deg2rad(self.sweep_field_polar)) + self.bias_field_z
                self.magnet.set_field_cartesian(Bx, By, Bz)
                while not self.magnet.check_field_cartesian(Bx, By, Bz, 2e-3):
                    sleep(0.5)
                x,y,z = self.magnet.get_field_cartesian()
                log.info(f"Field set to {x}, {y}, {z}")

            elif self.apply_bias_field == False:
                self.magnet.set_field_polar(field, self.sweep_field_azimuth, self.sweep_field_polar)
                while not self.magnet.check_field_polar(field, self.sweep_field_azimuth, self.sweep_field_polar, 2e-3):
                    sleep(0.5)
                x,y,z = self.magnet.get_field_cartesian()
                log.info(f"Field set to {x}, {y}, {z}")

            self.emit("progress", int(100*progress_iterator/num_progress))
            self.lockin.sub(0)
            self.lockin.sub(1)
            self.lockin.sub(2)
            self.lockin.sub(3)
            self.lockin.sub(4)
            self.lockin.sub(5)

            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,2,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}
            
            self.lockin.unsubscribe("*")

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[2]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[2]['x'],
                "Y2": dat[2]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[2]['y'],
                "DeltaThetaK_DualSideband": J2J1*(dat[4]['x'] + dat[5]['x'])/2/dat[2]['y'],
                "DeltaX1_C-M": dat[4]['x'],
                "DeltaY1_C-M": dat[4]['y'],
                "DeltaX1_C+M": dat[5]['x'],
                "DeltaY1_C+M": dat[5]['y'],
                "TX1": dat[0]['x'],
                "TY1": dat[0]['y'],
                "TX2": dat[1]['x'],
                "TY2": dat[1]['y'],
                "sweep_field": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break
        # current_voltage = self.lockin.get_vout(1, 6) * 10
        # ramp_down_voltages = np.arange(current_voltage, 0, -0.1)
        # for v in ramp_down_voltages: 
        #     v = float(v)
        #     if np.isclose(0, v, atol=0.001):
        #         v = 0
        #     self.lockin.set_vout(1, 6, v/10)
            # print(i)


    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        self.device.magnet.setHSetPoint3D(0.0, 0.0, 0.0)
        while (abs(self.device.magnet.getH(0)) > 0.001):
            sleep(2)
        log.info(f"Field set to {0}T")



class sagnacOpticsXportProcedure_vm_highZ(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')
    device = cr("192.168.1.1")

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_field_start = FloatParameter("Bias Magnetic Field start", units="T", default=0.1)
    sweep_field_stop = FloatParameter("Bias Magnetic Field stop", units="T", default=0.1)
    sweep_field_step = FloatParameter("Bias Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2","sweep_field","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        # print("Setting up Z magnet")
        log.info("Setting up Z magnet")
        # self.magnet = vectorMagnetZ("GPIB::24") #Connecting to Z
        self.device.connect()
        log.info("Connection with magnet established")

        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to the Zurich Lock-in")
        
        self.lockin = HF2LI(8005, 1, 18338)
        log.info(f'Outputing {self.applied_voltage} on output 2 osc 0')
        self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True
        
        # self.stepper = ANC150("COM3")
        # if self.x_enable:
        #     log.info("X enabled")
        #     self.stepper.set_mode(self.x_axis, 'stp')
        # if self.y_enable:
        #     log.info("y enabled")
        #     self.stepper.set_mode(self.y_axis, 'stp')

    def execute(self):
        # if self.x_enable:
        #     log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
        #     if self.delta_x >= 0:
        #         self.stepper.stepu(1, self.delta_x)
        #     else:
        #         self.stepper.stepd(1, -self.delta_x)
        # if self.y_enable:
        #     log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
        #     if self.delta_y >= 0:
        #         self.stepper.stepu(2, self.delta_y)
        #     else:
        #         self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        if self.sweep_field_start>self.sweep_field_stop and self.sweep_field_step>0:
            self.sweep_field_step= -1 * self.sweep_field_step
        field_points = np.arange(self.sweep_field_start,
                                 self.sweep_field_stop,
                                 self.sweep_field_step)
        if self.sweep_field_stop not in field_points:
            field_points = np.append(field_points,self.sweep_field_stop)
        if self.reverse:
            field_points = field_points[::-1]

        # field_points = np.append(field_points,
        #                          -1*field_points[::-1][1:])
        
        if self.saturate:

            self.device.magnet.setHSetPoint(0, self.saturating_field)
            while not np.isclose(self.saturating_field, self.device.magnet.getH(0), 0.002):
                sleep(0.5)

        if self.hysteresis:                        
            field_points = np.append(field_points, field_points[::-1][1:])

        if self.reverse:
            field_points = field_points[::-1]
        print("check field points: ", field_points)
        
        num_progress = field_points.size
        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info("Setting field to %g T" % field)
            self.device.magnet.setHSetPoint(0, field)
            log.info("waiting till field is set to setpoint")
            sleep(0.1)
            # if self.should_stop():
            #     log.info("Caught stop flag in procedure.")
            #     break

            # while self.magnet.is_ramping():
            #     sleep(2)
            #     log.info("Magnet is ramping")
            #     if self.should_stop():
            #         log.info("Caught stop flag in procedure.")
            #         break

            while not np.isclose(field, self.device.magnet.getH(0), 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            #Checking magnet's status to ensure that it successfully reaches the
            #setpoint without quenching or zeroing
           
            # if self.magnet.is_holding():
            #     log.info("Field set to %g T magnet status is HOLDING" % (field))
            # elif self.magnet.is_zeroing() or self.magnet.is_quenched():
            #     log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
            #     raise ValueError('Quench detected. Aborting procedures!')
            # else:
            #     log.warning("Could not reach setpoint. Exiting procedures and aborting")
            #     break
            # if self.should_stop():
            #     log.info("Caught stop flag in procedure.")
            #     break

            # rec_Bz = self.magnet.field
            # sleep(0.5)
            # if self.should_stop():
            #     log.info("Caught stop flag in procedure.")
            #     break
            
            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,2,3,4,5], ['x','y'], ratio=False))
                # log.info(self.lockin.poll_and_unpack(0.02, 100, [0,1,2,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[2]['y'])/2, # mode 4 (1st harmonic) / mode 3(second harmonic)
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[2]['x'],
                "Y2": dat[2]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[2]['y'],
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "TX1": dat[0]['x'],
                "TY1": dat[0]['y'],
                "TX2": dat[1]['x'],
                "TY2": dat[1]['y'],
                "sweep_field": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        # self.magnet.shutdown()
        # while self.magnet.is_ramping():
        #     sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
        #         #checking the status for every 22 Gauss change

        Bz= self.device.magnet.getH(0)
        # if self.magnet.is_holding() and np.isclose(Bz,0,atol=5e-3):
        #     log.info("%s" %self.status)
        #     log.info("Field set to 0T. Finished shutting down")
        # else:
        #     log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")
        # self.stepper.shut_down()
        # self.lockin.shutdown()
        self.device.magnet.setHSetPoint3D(0.0, 0.0, 0.0)
        while (abs(self.device.magnet.getH(0)) > 0.001):
            sleep(2)
        log.info(f"Field set to {0}T")

class sagnacOpticsXportPulseCurrentProcedure_vm(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    sweep_current_0 = FloatParameter("Current", units="A", default=0.0)
    sweep_current_1 = FloatParameter("Current End", units="A", default=0.0)
    sweep_current_2 = FloatParameter("Current Step", units="A", default=0.0)
    sweep_current_3 = FloatParameter("Current Step", units="A", default=0.0)
    sweep_current_num_1 = IntegerParameter("Number of current steps 1", default=1)
    sweep_current_num_2 = IntegerParameter("Number of current steps 2", default=1)
    pulsewidth = FloatParameter("Current Pulsewidth", units="s", default=1e-4)

    sweep_field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2","sweep_current","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        self.magnet = vectorMagnetFull(device) #X,Y,Z in that order

        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to sourcemeter 2400")
        self.sourcemeter = Keithley2400("GPIB::4")

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        # self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True
        
        # self.stepper = ANC150("COM3")
        # if self.x_enable:
        #     log.info("X enabled")
        #     self.stepper.set_mode(self.x_axis, 'stp')
        # if self.y_enable:
        #     log.info("y enabled")
        #     self.stepper.set_mode(self.y_axis, 'stp')

    def execute(self):
        # if self.x_enable:
        #     log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
        #     if self.delta_x >= 0:
        #         self.stepper.stepu(1, self.delta_x)
        #     else:
        #         self.stepper.stepd(1, -self.delta_x)
        # if self.y_enable:
        #     log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
        #     if self.delta_y >= 0:
        #         self.stepper.stepu(2, self.delta_y)
        #     else:
        #         self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.

        I_low = np.linspace(self.sweep_current_0, self.sweep_current_1, self.sweep_current_num_1).tolist()
        I_high = np.linspace(self.sweep_current_2, self.sweep_current_3, self.sweep_current_num_2).tolist()
        I_pos = I_low + I_high
        I_neg = (-np.array(I_pos)).tolist()
        current_points = I_pos + I_pos[-2:0:-1] + I_neg + I_neg[-2:0:-1] + I_pos
        
        if self.saturate:
            self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
            log.info("Setting saturation field")
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
        
        if not self.apply_bias_field:
            self.magnet.set_field_polar(self.sweep_field, self.sweep_field_azimuth, self.sweep_field_polar)
            log.info(f'B: {self.sweep_field}, phi: {self.sweep_field_azimuth}, theta: {self.sweep_field_polar}')
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(self.sweep_field, self.sweep_field_azimuth, self.sweep_field_polar, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

        else:
            Bx = self.sweep_field*np.sin(self.sweep_field_polar*deg2rad)*np.cos(self.sweep_field_azimuth*deg2rad)  + self.bias_field_x
            By = self.sweep_field*np.sin(self.sweep_field_polar*deg2rad)*np.sin(self.sweep_field_azimuth*deg2rad) + self.bias_field_y
            Bz = self.sweep_field*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_z
            log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
            self.magnet.set_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad)

            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
        
        log.info("Waiting a while to equilibrate")
        sleep(self.wait)

        num_progress = np.array(current_points).size
        start_time = time()

        for progress_iterator, current in enumerate(current_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info(f"I: {current} A, for {self.pulsewidth} s")
            
            self.lockin.set_vout(1,0,0)
            sleep(2)
            self.sourcemeter.ramp_to_current(current, steps = 4, pause = self.pulsewidth)
            sleep(self.pulsewidth)
            self.sourcemeter.ramp_to_current(0, steps = 4, pause = self.pulsewidth)
            sleep(2)
            self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
            sleep(2)

            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y'],
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "TX1": dat[0]['x'],
                "TY1": dat[0]['y'],
                "TX2": dat[1]['x'],
                "TY2": dat[1]['y'],
                "sweep_current": current,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        self.magnet.shutdown()
        while self.magnet.is_ramping():
            sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
                #checking the status for every 22 Gauss change

        Bx, By, Bz = self.magnet.get_field_cartesian()
        if self.magnet.is_holding() and np.isclose(Bx,0,atol=5e-3) and np.isclose(By,0, atol=5e-3) and np.isclose(Bz,0,atol=5e-3):
            log.info("%s" %self.status)
            log.info("Field set to 0T. Finished shutting down")
        else:
            log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")
        # self.stepper.shut_down()

class sagnacOpticsXportPulseCurrentSignalRecoveryProcedure_vm(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """
    device = cr("192.168.1.1")
    magnet = vectorMagnetFull(device)
    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    sweep_current_0 = FloatParameter("Current", units="A", default=0.0)
    sweep_current_1 = FloatParameter("Current End", units="A", default=0.0)
    sweep_current_2 = FloatParameter("Current Step", units="A", default=0.0)
    sweep_current_3 = FloatParameter("Current Step", units="A", default=0.0)
    sweep_current_num_1 = IntegerParameter("Number of current steps 1", default=1)
    sweep_current_num_2 = IntegerParameter("Number of current steps 2", default=1)
    pulsewidth = FloatParameter("Current Pulsewidth", units="s", default=5e-3)

    sweep_field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2","sweep_current","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        

        log.info("waiting for the wait time")
        sleep(self.wait) 

        # log.info("Connecting to sourcemeter 2400")
        # self.sourcemeter = Keithley2400("GPIB::4")

        log.info("Connecting to Signal Recovery Lockin")
        self.signalrecovery = DSP7265(11)
        self.signalrecovery.voltage = self.applied_voltage

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005, 1, 18338)
        # self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))n
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        # self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True
        
        # self.stepper = ANC150("COM3")
        # if self.x_enable:
        #     log.info("X enabled")
        #     self.stepper.set_mode(self.x_axis, 'stp')
        # if self.y_enable:
        #     log.info("y enabled")
        #     self.stepper.set_mode(self.y_axis, 'stp')

    def execute(self):
        if self.x_enable:
            log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
            if self.delta_x >= 0:
                self.stepper.stepu(1, self.delta_x)
            else:
                self.stepper.stepd(1, -self.delta_x)
        if self.y_enable:
            log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
            if self.delta_y >= 0:
                self.stepper.stepu(2, self.delta_y)
            else:
                self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.

        I_low = np.linspace(self.sweep_current_0, self.sweep_current_1, self.sweep_current_num_1).tolist()
        I_high = np.linspace(self.sweep_current_2, self.sweep_current_3, self.sweep_current_num_2).tolist()
        I_pos = I_low + I_high
        I_neg = (-np.array(I_pos)).tolist()
        current_points = I_pos + I_pos[-2:0:-1] + I_neg + I_neg[-2:0:-1] + I_pos
        
        if self.saturate:
            self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
            log.info("Setting saturation field")
            # while self.magnet.is_ramping():
            #     sleep(2)
            #     if self.should_stop():
            #         log.info("Caught stop flag in procedure.")
            #         break

            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
            sleep(2)

            self.magnet.set_field_polar(0, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
            log.info("Setting to zero field")
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(0, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
        
            sleep(2)

        if not self.apply_bias_field:
            self.magnet.set_field_polar(self.sweep_field, self.sweep_field_azimuth, self.sweep_field_polar)
            log.info(f'B: {self.sweep_field}, phi: {self.sweep_field_azimuth}, theta: {self.sweep_field_polar}')
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(self.sweep_field, self.sweep_field_azimuth, self.sweep_field_polar, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

        else:
            Bx = self.sweep_field*np.sin(self.sweep_field_polar*deg2rad)*np.cos(self.sweep_field_azimuth*deg2rad)  + self.bias_field_x
            By = self.sweep_field*np.sin(self.sweep_field_polar*deg2rad)*np.sin(self.sweep_field_azimuth*deg2rad) + self.bias_field_y
            Bz = self.sweep_field*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_z
            log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
            self.magnet.set_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad)

            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
        
        log.info("Waiting a while to equilibrate")
        sleep(self.wait)

        num_progress = np.array(current_points).size
        start_time = time()

        for progress_iterator, current in enumerate(current_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info(f"I: {current} A, for {self.pulsewidth} s")
            
            self.signalrecovery.voltage = 0.0
            sleep(2)
            self.sourcemeter.ramp_to_current(current, steps = 4, pause = self.pulsewidth)
            sleep(self.pulsewidth)
            self.sourcemeter.ramp_to_current(0, steps = 4, pause = self.pulsewidth)
            sleep(2)
            self.signalrecovery.voltage = self.applied_voltage
            sleep(2)

            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y'],
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "TX1": self.signalrecovery.x1,
                "TY1": self.signalrecovery.y1,
                "TX2": self.signalrecovery.x2,
                "TY2": self.signalrecovery.y2,
                # "TX2": dat[1]['x'],
                # "TY2": dat[1]['y'],
                "sweep_current": current,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        self.signalrecovery.voltage = 0.0
        # self.stepper.shut_down()
        # self.magnet.shutdown()
        # while self.magnet.is_ramping():
        #     sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
        #         #checking the status for every 22 Gauss change


        # Bx, By, Bz = self.magnet.get_field_cartesian()
        # if self.magnet.is_holding() and np.isclose(Bx,0,atol=5e-3) and np.isclose(By,0, atol=5e-3) and np.isclose(Bz,0,atol=5e-3):
        #     log.info("%s" %self.status)
        #     log.info("Field set to 0T. Finished shutting down")
        # else:
        #     log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")

class sagnacOpticsXportSignalRecoveryProcedure_vm_highZ(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
    sweep_field_step = FloatParameter("Bias Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2","sweep_field","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        print("Setting up Z magnet")
        log.info("Setting up Z magnet")
        self.magnet = vectorMagnetZ("GPIB::21") #Connecting to Z
        log.info("Connection with magnet established")

        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to Signal Recovery Lockin")
        self.signalrecovery = DSP7265(3)
        self.signalrecovery.voltage = self.applied_voltage

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        # log.info(f'Outputing {self.applied_voltage} on output 2 osc 0')
        # self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        # self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True
        
        # self.stepper = ANC150("COM3")
        # if self.x_enable:
        #     log.info("X enabled")
        #     self.stepper.set_mode(self.x_axis, 'stp')
        # if self.y_enable:
        #     log.info("y enabled")
        #     self.stepper.set_mode(self.y_axis, 'stp')

    def execute(self):
        if self.x_enable:
            log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
            if self.delta_x >= 0:
                self.stepper.stepu(1, self.delta_x)
            else:
                self.stepper.stepd(1, -self.delta_x)
        if self.y_enable:
            log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
            if self.delta_y >= 0:
                self.stepper.stepu(2, self.delta_y)
            else:
                self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        field_points = np.arange(0,
                                 self.sweep_field,
                                 self.sweep_field_step)
        if self.sweep_field not in field_points:
            field_points = np.append(field_points,self.sweep_field)
        
        field_points = field_points[::-1]

        field_points = np.append(field_points,
                                 -1*field_points[::-1][1:])
        if self.hysteresis:                        
            field_points = np.append(field_points, field_points[::-1][1:])

        if self.reverse:
            field_points = field_points[::-1]
        
        num_progress = field_points.size
        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            log.info("Setting field to %g T" % field)
            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
                sleep(0.5)
            log.info("waiting till field is set to setpoint")
            sleep(0.1)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break

            # while self.magnet.is_ramping():
            #     sleep(2)
            #     log.info("Magnet is ramping")
            #     if self.should_stop():
            #         log.info("Caught stop flag in procedure.")
            #         break

            while not np.isclose(field,self.magnet.field, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            #Checking magnet's status to ensure that it successfully reaches the
            #setpoint without quenching or zeroing
           
            if self.magnet.is_holding():
                log.info("Field set to %g T magnet status is HOLDING" % (field))
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
                break
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break

            rec_Bz = self.magnet.field
            sleep(0.5)
            if self.should_stop():
                log.info("Caught stop flag in procedure.")
                break
            
            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y'],
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "TX1": self.signalrecovery.x1,
                "TY1": self.signalrecovery.y1,
                "TX2": self.signalrecovery.x2,
                "TY2": self.signalrecovery.y2,
                "sweep_field": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        self.stepper.shut_down()
        self.signalrecovery.voltage = 0.0
        self.magnet.shutdown()
        while self.magnet.is_ramping():
            sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
                #checking the status for every 22 Gauss change

        Bz= self.magnet.field
        if self.magnet.is_holding() and np.isclose(Bz,0,atol=5e-3):
            log.info("%s" %self.status)
            log.info("Field set to 0T. Finished shutting down")
        else:
            log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")

class sagnacOpticsXportSignalRecoveryProcedure_vm(Procedure):
    """
    Procedure for taking Heterodyne Hysteresis Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
    # apply_current = BooleanParameter("Current Applied?", default=True)
    # current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    # current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
    sweep_field_step = FloatParameter("Bias Magnetic Field step", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2","sweep_field","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        self.magnet = vectorMagnetFull("GPIB::23", "GPIB::22", "GPIB::21") #X,Y,Z in that order

        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to Signal Recovery Lockin")
        self.signalrecovery = DSP7265(3)
        self.signalrecovery.voltage = self.applied_voltage

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)
        self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
        #subscribe to outputs
        self.lockin.sub(0)
        self.lockin.sub(1)
        # self.lockin.sub(2)
        self.lockin.sub(3)
        self.lockin.sub(4)
        self.lockin.sub(5)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True
        
        self.stepper = ANC150("COM3")
        # self.stepper.set_f(self.x_axis, 1000)
        # self.stepper.set_v(self.x_axis, 35)
        if self.x_enable:
            log.info("X enabled")
            self.stepper.set_mode(self.x_axis, 'stp')
        # self.stepper.set_f(self.y_axis, 1000)
        # self.stepper.set_v(self.y_axis, 32)
        if self.y_enable:
            log.info("y enabled")
            self.stepper.set_mode(self.y_axis, 'stp')

    def execute(self):
        if self.x_enable:
            log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
            if self.delta_x >= 0:
                self.stepper.stepu(1, self.delta_x)
            else:
                self.stepper.stepd(1, -self.delta_x)
        if self.y_enable:
            log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
            if self.delta_y >= 0:
                self.stepper.stepu(2, self.delta_y)
            else:
                self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        field_points = np.arange(0,
                                 self.sweep_field,
                                 self.sweep_field_step)
        if self.sweep_field not in field_points:
            field_points = np.append(field_points,self.sweep_field)
        
        field_points = field_points[::-1]

        field_points = np.append(field_points,
                                 -1*field_points[::-1][1:])
        if self.hysteresis:                        
            field_points = np.append(field_points, field_points[::-1][1:])

        if self.reverse:
            field_points = field_points[::-1]
        
        if self.saturate:
            self.magnet.set_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar)  #saturate the field 
            log.info("Setting saturation field")
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(self.saturating_field, self.saturating_field_azimuth, self.saturating_field_polar, 5e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
        
        if not self.apply_bias_field:
            self.magnet.set_field_polar(field_points[0], self.sweep_field_azimuth, self.sweep_field_polar)
            log.info(f'B: {field_points[0]}, phi: {self.sweep_field_azimuth}, theta: {self.sweep_field_polar}')
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(field_points[0], self.sweep_field_azimuth, self.sweep_field_polar, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

        else:
            Bx = field_points[0]*np.sin(self.sweep_field_polar*deg2rad)*np.cos(self.sweep_field_azimuth*deg2rad)  + self.bias_field_x
            By = field_points[0]*np.sin(self.sweep_field_polar*deg2rad)*np.sin(self.sweep_field_azimuth*deg2rad) + self.bias_field_y
            Bz = field_points[0]*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_z
            log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
            self.magnet.set_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad)

            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")
        
        log.info("Waiting a while to equilibrate")
        sleep(self.wait)

        num_progress = field_points.size
        start_time = time()

        for progress_iterator, field in enumerate(field_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            if not self.apply_bias_field:
                self.magnet.set_field_polar(field, self.sweep_field_azimuth, self.sweep_field_polar)
                log.info(f'B: {field}, phi: {self.sweep_field_azimuth}, theta: {self.sweep_field_polar}')
                while self.magnet.is_ramping():
                    sleep(2)
                    if self.should_stop():
                        log.info("Caught stop flag in procedure.")
                        break

                while not self.magnet.check_field_polar(field, self.sweep_field_azimuth, self.sweep_field_polar, 2e-3):
                    sleep(0.5)
                    if self.should_stop():
                        log.info("Caught stop flag in procedure.")
                        break

                if self.magnet.is_holding():
                    log.info(" magnet status is HOLDING" )
                elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                    log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                    raise ValueError('Quench detected. Aborting procedures!')
                elif self.should_stop():
                    log.info("Caught stop flag in procedure.")
                else:
                    log.warning("Could not reach setpoint. Exiting procedures and aborting")
                    log.info(f"Setting Magnetic Field to {field:.5f} T")
            else:
                Bx = field*np.sin(self.sweep_field_polar*deg2rad)*np.cos(self.sweep_field_azimuth*deg2rad)  + self.bias_field_x
                By = field*np.sin(self.sweep_field_polar*deg2rad)*np.sin(self.sweep_field_azimuth*deg2rad) + self.bias_field_y
                Bz = field*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_z
                log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
                self.magnet.set_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad)

                while self.magnet.is_ramping():
                    sleep(2)
                    if self.should_stop():
                        log.info("Caught stop flag in procedure.")
                        break

                while not self.magnet.check_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arcsin(By/Bx)/deg2rad, np.arcsin(np.sqrt(Bx**2 + By**2)/Bz)/deg2rad, 2e-3):
                    sleep(0.5)
                    if self.should_stop():
                        log.info("Caught stop flag in procedure.")
                        break

                if self.magnet.is_holding():
                    log.info(" magnet status is HOLDING" )
                elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                    log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                    raise ValueError('Quench detected. Aborting procedures!')
                elif self.should_stop():
                    log.info("Caught stop flag in procedure.")
                else:
                    log.warning("Could not reach setpoint. Exiting procedures and aborting")
            
            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[5]['x'],
                "Y2": dat[5]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y'],
                "DeltaX1": dat[4]['x'],
                "DeltaY1": dat[4]['y'],
                "TX1": self.signalrecovery.x1,
                "TY1": self.signalrecovery.y1,
                "TX2": self.signalrecovery.x2,
                "TY2": self.signalrecovery.y2,
                "sweep_field": field,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        self.stepper.shut_down()
        self.signalrecovery.voltage = 0.0
        self.magnet.shutdown()
        while self.magnet.is_ramping():
            sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
                #checking the status for every 22 Gauss change

        Bx, By, Bz = self.magnet.get_field_cartesian()
        if self.magnet.is_holding() and np.isclose(Bx,0,atol=5e-3) and np.isclose(By,0, atol=5e-3) and np.isclose(Bz,0,atol=5e-3):
            log.info("%s" %self.status)
            log.info("Field set to 0T. Finished shutting down")
        else:
            log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")
        
class sagnacOpticsXportVoltageSweepProcedure_vm(Procedure):
    """
    Procedure for taking Voltage Sweep Measurements 
    with the Sagnac setup
    """

    calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
    sample_name = Parameter("Sample Name",default='test')

    step = IntegerParameter("current step", default = 0)
    delta_x = IntegerParameter("stepper x step", default = 0)
    delta_y = IntegerParameter("stepper y step", default = 0)
    x_axis = 1
    y_axis = 2
    x_enable = BooleanParameter("Enable x motion", default = True)
    y_enable = BooleanParameter("Enable y motion", default = False)

    voltage_start = FloatParameter("Applied Sample Voltage Start", units="V", default=0)
    voltage_stop = FloatParameter("Applied Sample Voltage End", units="V", default=0)
    voltage_step = FloatParameter("Applied Sample Voltage Step", units="V", default=0)

    current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
    settling = FloatParameter("Settling", units="s", default=0.5)
    wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
    avgs = IntegerParameter("Number of Averages", default = 1)
    amp_gain = FloatParameter("Amp Gain", units="x", default=1)

    saturate = BooleanParameter("Saturate First?", default=True)
    saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
    saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
    saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

    hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
    reverse = BooleanParameter("Reverse?", default=False)
    sweep_field = FloatParameter("Bias Magnetic Field start", units="T", default=0.1)
    sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
    sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

    apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
    bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
    bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
    bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

    input_range = FloatParameter("input range", units="V", default=1)
    imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)
    f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

    first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
    second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
    first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
    second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

    eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
    queued_time = Parameter('Time Queued')

    first = True
    last = True

    DATA_COLUMNS = ["ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaThetaK_DualSideband", "DeltaX1_C-M", "DeltaY1_C-M", "DeltaX1_C+M", "DeltaY1_C+M","TX1","TY1","TX2","TY2","voltage","elapsed_time"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        print("Setting up X,Y,Z magnets")
        log.info("Setting up X,Y,Z magnets")
        self.magnet = vectorMagnetFull("GPIB::26", "GPIB::25", "GPIB::24") #X,Y,Z in that order
        self.z_magnet = vectorMagnetZ("GPIB::24")

        log.info("waiting for the wait time")
        sleep(self.wait) 

        log.info("Connecting to the Zurich Lock-in")
        self.lockin = HF2LI(8005,1,1004)

        self.apply_bias_field = False
        if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
            self.apply_bias_field = True

        self.stepper = ANC300()
        self.stepper.connect()

    def execute(self):
        if self.x_enable:
            log.info(f'Now at step number {self.step}, moving sample by x:{self.delta_x}')
            if self.delta_x >= 0:
                self.stepper.stepu(1, self.delta_x)
            else:
                self.stepper.stepd(1, -self.delta_x)
        if self.y_enable:
            log.info(f'Now at step number {self.step}, moving sample by y:{self.delta_y}')
            if self.delta_y >= 0:
                self.stepper.stepu(2, self.delta_y)
            else:
                self.stepper.stepd(2, -self.delta_y)

        J2J1 = 0.543
        J1J0 = 1.837
        deg2rad = np.pi/180.
        voltage_points = np.arange(self.voltage_start,
                                 self.voltage_stop,
                                 self.voltage_step)
        if self.voltage_stop not in voltage_points:
            voltage_points = np.append(voltage_points,self.voltage_stop)
            
        if self.hysteresis:                        
            voltage_points = np.append(voltage_points, voltage_points[::-1][1:])
        
        if self.saturate:
            self.z_magnet.field = self.saturating_field
            log.info("Setting saturation field")
            sleep(0.1)

            while self.z_magnet.is_ramping():
                sleep(2)
                log.info("Magnet is ramping")
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not np.isclose(self.saturating_field, self.z_magnet.field, atol = 5e-5):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            #Checking magnet's status to ensure that it successfully reaches the
            #setpoint without quenching or zeroing
           
            if self.z_magnet.is_holding():
                log.info("Field set to %g T magnet status is HOLDING" % (self.saturating_field))
            elif self.z_magnet.is_zeroing() or self.z_magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

        #Applying Magnetic Field
        if not self.apply_bias_field:
            self.magnet.set_field_polar(self.sweep_field, self.sweep_field_azimuth, self.sweep_field_polar)
            log.info(f'B: {self.sweep_field}, phi: {self.sweep_field_azimuth}, theta: {self.sweep_field_polar}')
            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(self.sweep_field, self.sweep_field_azimuth, self.sweep_field_polar, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

        else:
            Bx = self.sweep_field*np.sin(self.sweep_field_polar*deg2rad)*np.cos(self.sweep_field_azimuth*deg2rad)  + self.bias_field_x
            By = self.sweep_field*np.sin(self.sweep_field_polar*deg2rad)*np.sin(self.sweep_field_azimuth*deg2rad) + self.bias_field_y
            Bz = self.sweep_field*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_z
            log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
            self.magnet.set_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arctan2(By,Bx)/deg2rad, np.arctan2(np.sqrt(Bx**2 + By**2),Bz)/deg2rad)

            while self.magnet.is_ramping():
                sleep(2)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            while not self.magnet.check_field_polar(np.sqrt(Bx**2 + By**2 + Bz**2), np.arctan2(By,Bx)/deg2rad, np.arctan2(np.sqrt(Bx**2 + By**2),Bz)/deg2rad, 2e-3):
                sleep(0.5)
                if self.should_stop():
                    log.info("Caught stop flag in procedure.")
                    break

            if self.magnet.is_holding():
                log.info(" magnet status is HOLDING" )
            elif self.magnet.is_zeroing() or self.magnet.is_quenched():
                log.info('Field abruptly set to ZERO or Magnet quench detected. Aborting procedures.')
                raise ValueError('Quench detected. Aborting procedures!')
            elif self.should_stop():
                log.info("Caught stop flag in procedure.")
            else:
                log.warning("Could not reach setpoint. Exiting procedures and aborting")

        num_progress = voltage_points.size
        start_time = time()

        for progress_iterator, voltage in enumerate(voltage_points):
            self.emit("progress", 100*progress_iterator/num_progress)
            self.lockin.set_vout(1,6,voltage/10*np.sqrt(2))
            log.info("Waiting a while to equilibrate")
            sleep(self.wait)

            self.lockin.sub(0)
            self.lockin.sub(1)
            self.lockin.sub(2)
            self.lockin.sub(3)
            self.lockin.sub(4)
            self.lockin.sub(5)

            dat_list = []
            for i in range(self.avgs):
                self.lockin.sync() # clears buffer since field has changed
                sleep(self.settling)
                self.lockin.sync() # clears buffer since field has changed
                log.info("recording average #%d"%i)
                dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,2,3,4,5], ['x','y'], ratio=False))
            dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

            self.lockin.unsubscribe("*")

            log.info("Recording results")
            self.emit('results', {
                "ThetaK": np.arctan(J2J1*dat[3]['x']/dat[2]['y'])/2, 
                "X1": dat[3]['x'],
                "Y1": dat[3]['y'],
                "X2": dat[2]['x'],
                "Y2": dat[2]['y'],
                "DeltaThetaK": J2J1*dat[4]['x']/dat[2]['y'],
                "DeltaThetaK_DualSideband": J2J1*(dat[4]['x'] + dat[5]['x'])/2/dat[2]['y'],
                "DeltaX1_C-M": dat[4]['x'],
                "DeltaY1_C-M": dat[4]['y'],
                "DeltaX1_C+M": dat[5]['x'],
                "DeltaY1_C+M": dat[5]['y'],
                "TX1": dat[0]['x'],
                "TY1": dat[0]['y'],
                "TX2": dat[1]['x'],
                "TY2": dat[1]['y'],
                "voltage": voltage,
                "elapsed_time": time()-start_time
                })
            if self.should_stop():
                log.warning("Caught stop flag in procedure.")
                break

    def shutdown(self):
        log.info("Finished with scans. Shutting down instruments.")
        # self.magnet.shutdown()
        # while self.magnet.is_ramping():
        #     sleep(1) #For ramp rate of 0.043T/sec this is equivalent to
        #         #checking the status for every 22 Gauss change

        # Bx, By, Bz = self.magnet.get_field_cartesian()
        # if self.magnet.is_holding() and np.isclose(Bx,0,atol=5e-3) and np.isclose(By,0, atol=5e-3) and np.isclose(Bz,0,atol=5e-3):
        #     log.info("%s" %self.status)
        #     log.info("Field set to 0T. Finished shutting down")
        # else:
        #     log.warning("Could not ramp field to zero at ramp rate. Using zeroing mode")
        self.lockin.set_vout(1,6,0)