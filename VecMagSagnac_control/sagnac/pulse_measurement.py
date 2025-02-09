from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa
from .instruments.AMI420 import AMI420
from sagnac.instruments import APS100
import atto_device.CRYO2100 as cr
import os
import numpy as np
import pandas as pd
from zhinst.toolkit import Session

from pymeasure.instruments.keithley import Keithley2400
from aparatus.sagnac3 import myHF2LI

#Pseudocode from Thow:
#Voltages = []
# for current in currents:
#          self.zurich.output_voltage = 0
#          sleep(0.5)
#          self.keithley.source_current = current
#          sleep(pulse_duration)
#          self.keithley.source_current = 0
#          sleep(0.5)
#          self.zurich.output_voltage = 0.1
#          sleep(4*time_constant)
#          Voltages.append(self.zurich.voltage)
#           #Code to update plots (edited) 


class Pulse:

    def __init__(self):
        ## Ethan does not know what needs to go here and would love help
        self.keith1 = Keithley2400("GPIB::26") #currently NI Max is reading as GPIB::26
        print(f"Check that output on Keithley is on")
        pulsecurrent = 0
        self.keith1.enable_source()
        self.keith1.measure_resistance()
    
    # def get_current(self):
    #     return self.keith1.current() 

    # def set_current(self,Ipulse):
    #     self.keith1.source_current(Ipulse)

    # current = property(get_current,set_current)
    
    def send_pulse(self, width):
        
        # #Ethan is not sure whether it is possible to set Zurich to 0 in this class and
        # #as such has put it in the pulse_measurement.csv file for example

        # # After discussion this section was moved directly into the csv for clarity

        # #set output from Zurich to 0
        # print(f"Setting Zurich Output to 0 Vac")
        # self.myHF2LI.ac = 0
        # sleep(0.5)

        # #raise current limit on Keithley and then apply current
        # print(f"Sending {self._current} A for {width} second pulse")
        # self.set_current(self._current)
        # self.keith1.apply_current()
        # sleep(width)

        # #set current back to 0
        # self.set_current(0)
        # self.keith1.apply_current()
        # sleep(0.5)

        #set current to pulse height
        print(f"Sending {self.pulsecurrent} A for {width} second pulse")
        # print(type(self.pulsecurrent))
        # print(f"Type of source_current: {type(self.keith1.source_current)}") 
        # self.keith1.source_current(self.pulsecurrent)
        self.keith1.source_current = self.pulsecurrent
        # self.keith1.apply_current()
    
        #set current back to 0
        self.keith1.source_current = 0
        # self.keith1.apply_current()
        sleep(0.5)

         
    




    


