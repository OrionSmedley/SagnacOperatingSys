from time import sleep
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa
from .instruments.AMI420 import AMI420

def handle_timeout(fail_mode):
    def handle_timeout_decorator(func):
        def func_wrapper(self, *args, **kwargs):
            esp_faliure_counter = 0
            esp_success = False
            FALIURE_LIMIT = 10
            while esp_faliure_counter < FALIURE_LIMIT:
                try:
                    return func(self, *args, **kwargs)
                except pyvisa.errors.VisaIOError:
                    esp_faliure_counter += 1
                    log.warning("failed {mode}, at count {count} of {max}".format(
                        mode=fail_mode,
                        count=esp_faliure_counter,
                        max=FALIURE_LIMIT
                        )
                    )
                    log.info("Clearing GPIB connection %s"%self.name)
                    self.adapter.manager.visalib.clear(self.adapter.connection.session)
                    continue
                esp_success = True # only runs if we beat try statement
                break
            if not esp_success:
                raise RuntimeError("Not able to successfully communicate with ESP300")
        return func_wrapper
    return handle_timeout_decorator

# NOTE: magnet is controlled with field

class vectormagnet_field_x(AMI420):
    """This is the pseudo instrument class for independently controlling
    X field of the vector magnet in H8"""

    DELAY = 0.05

    def __init__(self, resourceName, **kwargs):
        """Setting up power supply/controller parameters and setting to remote
        mode"""
        delay = 0.05
        super().__init__(resourceName, **kwargs)
        self.name = "Vector Magnet X Axis"
        # self.remote() #Stay in local mode so that can control programmer from
        # front panel in case something goes wrong

        #Using SI units for Voltage, current, field and ramp rate
        self.field_units = 'tesla'
        self.ramp_rate_units ='seconds'

        print('set units')
        sleep(delay)

        #Setting the min, max output paramters for AMI4Q05100PS
        self.current_minimum = -100
        self.current_maximum = 100
        self.voltage_maximum = 5
        self.voltage_minimum = -5

        print('set current voltage max min')
        sleep(delay)

        #Stability setting should be close to zero when magnet is connected to
        #circuit. If testing the supplies without magnet, use 100%
        #self.stability = 50

        #print('set stability')
        #sleep(delay)

        #Value taken from Manual, also referred to as field to current ratio
        self.coil_constant = 0.018891  #Telsa/Amp

        print('set coil constant')
        sleep(delay)

        #Setting the max current to attain a max field of 6.045705 T,
        #~1T less than the maximum rated field
        self.magnet_current_limit = 47.5 #Amps #This keeps the max field to 0.8973225 T

        print('set current limit')
        sleep(delay)

        #Fixing the ramp rate, calculated assuming L=7.8 Henries
        #Max ramp rate = 0.0861 T/sec for max 5V from power supply
        #Setting it to be 0.043 T/sec which corresponds to 320mA/sec which is
        #within ramp rate range for AMI420
        #self.field_ramp_rate = 0.0043 #T/sec CHANGED FROM 0.043 T/sec

        #print('set field ramp rate')
        #sleep(delay)

        #What does this do?
        self.auto_quench_detect = True

        print('set auto quench detect')
        sleep(delay)

        #Calculating the field limits given the coil constant and magnet
        #current limit
        field_limit = self.coil_constant*self.magnet_current_limit

        print('read successfully')
        self._fieldlims = [-1*field_limit, field_limit]

        print('set field limits and done')

    """This function sets the field to given setpoint"""
    @handle_timeout("setting field")
    def setField(self, nfield):
        if (nfield < self._fieldlims[0] or nfield > self._fieldlims[1]):
            log.warning("""Too much current applied to magnet. Staying at
                        previous setpoint""")
            log.info("%s" %self.state)

        else:
            self.set_ramp_mode()
            self.field_setpoint = nfield

    """Reads the field in the magnet coils"""
    @handle_timeout("getting field")
    def getField(self):
        return self.magnet_field

    field = property(getField, setField)

    @handle_timeout("ramping")
    def is_ramping(self):
        if self.state == 'Ramping':
            return True
        else:
            return False

    @handle_timeout("holding")
    def is_holding(self):
        if self.state == 'Holding':
            return True
        else:
            return False

    @handle_timeout("zeroing")
    def is_zeroing(self):
        if self.state == 'Zeroing':
            return True
        else:
            return False

    @handle_timeout("Quench detected")
    def is_quenched(self):
        if self.state == 'Quench':
            return True
        else:
            return False

    @handle_timeout("Paused")
    def is_paused(self):
        if self.state == 'Paused':
            return True
        else:
            return False

    """Shuts down the power supply i.e. brings the current to zero and returns
    to local mode"""
    @handle_timeout("Shutdown")
    def shutdown(self):
        """ Ensures the magnet is set to zero field """
        super().shutdown()
        self.field = 0. # turn field off
        sleep(0.1)
        self.local() #Can this be done manually from frontpanel?
