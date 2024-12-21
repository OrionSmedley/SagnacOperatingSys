import serial
import time
import numpy as np

class APS100:
    """
    Instrument class for the Attocube APS100 magnet power supply.
    Manages USB communication and provides methods to send commands and receive responses.
    """

    def __init__(self, port, baudrate=9600, timeout=2):
        """
        Initialize the APS100 connection.

        Args:
            port (str): The USB port (e.g., COM3, /dev/ttyUSB0).
            baudrate (int): Communication baud rate (default: 9600).
            timeout (float): Timeout for read operations in seconds (default: 2).
        """
        # if self.connection and self.connection.is_open:
        #     self.disconnect()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None

    def connect(self):
        """
        Open the serial connection to the APS100.
        """
        if self.connection and self.connection.is_open:
            print(f"connection is already open on {self.port}")
            self.disconnect()
        try:
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            print(f"Connected to APS100 on {self.port}")
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to APS100 on {self.port}: {e}")

    def disconnect(self):
        """
        Close the serial connection.
        """
        if self.connection:
            self.connection.close()
        print("Disconnected from APS100")

    def send_command(self, command):
        """
        Send a command to the APS100.

        Args:
            command (str): The command string to send (without newline).

        Returns:
            str: The response from the device.
        """
        if not self.connection or not self.connection.is_open:
            raise ConnectionError("Connection to APS100 is not open.")

        try:
            # Send command (append newline for termination)
            full_command = command + "\n"
            self.connection.write(full_command.encode('utf-8'))
            # print(f"Sent: {command}")

            # Read response
            time.sleep(1)  # Wait briefly for the device to respond
            response = self.connection.read(self.connection.in_waiting or 1)  # Read available data
            res = response.decode('utf-8').strip().split('\n', 1)[-1]
            return res

        except Exception as e:
            raise IOError(f"Failed to send command '{command}': {e}")

    def query_status(self):
        """
        Query the status of the APS100.

        Returns:
            str: Status information from the device.
        """
        return self.send_command("STATUS")

    def set_channel(self, channel):
        self.send_command(f'CHAN {int(channel)}')
        res = self.send_command('CHAN?')
        return res

    def get_field(self):
        res = self.send_command('IMAG?')
        value = float(res.replace('kG', ''))
        return value

    def set_field(self, field):
        # field in kG
        if abs(field) > 10:
            field = np.sign()*10
        
        current_field = self.get_field()
        time.sleep(0.1)
        if field - current_field > 0.001:
            self.send_command(f'ULIM {field}')
            time.sleep(0.1)
            self.send_command('SWEEP UP')
        elif field - current_field < -0.001:
            self.send_command(f'LLIM {field}')
            time.sleep(0.1)
            self.send_command('SWEEP DOWN')
        else:
            pass

    def check_field(self, set_field, tol = 0.001):
        current_field = self.get_field()
        if abs(set_field - current_field) > tol:
            return False
        else:
            return True
    
    def zero_field(self):
        current_field = self.get_field()
        if abs(current_field) > 0.001:
            self.send_command('SWEEP ZERO')