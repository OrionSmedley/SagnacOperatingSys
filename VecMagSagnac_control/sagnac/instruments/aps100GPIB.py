from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa


class APS100:
    """
    Instrument class for the Attocube APS100 magnet power supply.
    Manages GPIB communication and provides methods to send commands and receive responses.
    """
    def __init__(self, GPIB_Port):
        self.resourcestr = f"GPIB0::{GPIB_Port}::INSTR"
        self.instrument = None
        self._field_cache = 0
        self._temp_field_cache = 0

    def connect(self):
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(self.resourcestr)
        self.instrument.read_termination = '\n'
        self.instrument.write_termination = '\r\n'

    # def send_command(self, command):
    #     """
    #     Send a command to the APS100.

    #     Args:
    #         command (str): The command string to send (without newline).

    #     Returns:
    #         str: The response from the device.
    #     """
    #     if not self.connection or not self.connection.is_open:
    #         raise ConnectionError("Connection to APS100 is not open.")

    #     try:
    #         # Send command (append newline for termination)
    #         full_command = command + "\n"
    #         self.connection.write(full_command.encode('utf-8'))
    #         # print(f"Sent: {command}")

    #         # Read response
    #         time.sleep(1)  # Wait briefly for the device to respond
    #         response = self.connection.read(self.connection.in_waiting or 1)  # Read available data
    #         res = response.decode('utf-8').strip().split('\n', 1)[-1]
    #         return res

    #     except Exception as e:
    #         raise IOError(f"Failed to send command '{command}': {e}")

    def disconnect(self):
        if self.instrument:
            self.instrument.close()
    
    def query(self, command):
        badresponse = self.instrument.query(command)
        response = self.instrument.query(command)
        # print(response)
        return response

    def write(self, command):
        self.instrument.write(command)

    def query_status(self):
        """
        Query the status of the APS100.

        Returns:
            str: Status information from the device.
        """
        return self.query("STATUS")

    def set_channel(self, channel):
        self.write(f'CHAN {int(channel)}')
        value = np.nan
        while np.isnan(value):
            try:
                value = self.query('CHAN?')
                # print(value)
                return value
            except:
                value =  np.nan
                sleep(0.5)

    def get_field(self):
        value = np.NaN
        while np.isnan(value):
            try:
                res = self.query('IMAG?')
                value = float(res.replace('kG', ''))
                # self._field_cache = value
                # res = self.query('IMAG?')
                # value = float(res.replace('kG', ''))
                # if abs(value - self._field_cache) > 0.1:
                #     # print("Rechecking field")
                #     # sleep(0.1) 
                #     self._temp_field_cache = value
                #     res = self.query('IMAG?')
                #     value = float(res.replace('kG', ''))            
                #     while abs(value - self._temp_field_cache)/abs(self._temp_field_cache) > 0.5 and abs(value - self._field_cache) > 0.6:
                #         # sleep(0.1)
                #         self._temp_field_cache = value
                #         res = self.query('IMAG?')
                #         value = float(res.replace('kG', ''))    
                # self._field_cache = value
                return value
            except:
                value =  np.NaN
                sleep(0.5)

    def set_field(self, field):
        # field in kG
        if abs(field) > 90:
            field = np.sign(field)*90
        current_field = self.get_field()
        if field == 0:
            if self.is_ramping() == 'Standby' or self.is_ramping() == 'Sweeping to zero':
                pass
            else:
                self.zero_field()
        else:
            if field - current_field > 0.001:
                self.write(f'ULIM {field};')
                sleep(0.1)
                self.write('SWEEP UP')
            elif field - current_field < -0.001:
                self.write(f'LLIM {field};')
                sleep(0.1)
                self.write('SWEEP DOWN')
            else:
                pass

    def check_field(self, set_field, tol = 0.001):
        current_field = self.get_field()
        if abs(set_field - current_field) > tol:
            return False
        else:
            return True
        
    def is_ramping(self):
        check = self.query('SWEEP?')
        # print(f"Ramping check is {check}")
        return check
    
    def zero_field(self):
        self.write('SWEEP ZERO')