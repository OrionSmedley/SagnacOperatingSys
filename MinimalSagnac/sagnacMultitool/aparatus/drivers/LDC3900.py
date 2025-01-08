import pyvisa

# Configure the GPIB address for your device (replace with actual address)
GPIB_ADDRESS = "GPIB0::2::INSTR"

def initialize_device():
    """
    Initializes the connection to the GPIB device.
    """
    try:
        rm = pyvisa.ResourceManager()
        instrument = rm.open_resource(GPIB_ADDRESS)

        # Print device information to confirm connection
        idn = instrument.query("*IDN?")
        print(f"Connected to: {idn.strip()}")

        return instrument
    except pyvisa.VisaIOError as e:
        print(f"Error: Could not connect to device at {GPIB_ADDRESS}: {e}")
        return None

def send_command(instrument, command):
    """
    Sends a SCPI command to the device.
    """
    try:
        instrument.write(command)
        print(f"Command sent: {command}")
    except pyvisa.VisaIOError as e:
        print(f"Error sending command '{command}': {e}")

def query_device(instrument, command):
    """
    Queries the device and returns the response.
    """
    try:
        response = instrument.query(command)
        print(f"Response: {response.strip()}")
        return response
    except pyvisa.VisaIOError as e:
        print(f"Error querying command '{command}': {e}")
        return None

def set_laser_current(instrument, current):
    """
    Sets the laser current limit using the GPIB command.
    """
    try:
        # Ensure the current limit is in amperes
        command = f"LAS:LDI {current:.3f}"
        send_command(instrument, command)

        # Verify the current limit was set correctly
        response = query_device(instrument, "LAS:LDI?")
        print(f"Laser current limit confirmed: {response.strip()} mA")
        
    except Exception as e:
        print(f"Error setting laser current limit: {e}")

def get_laser_current(instrument):
    """
    Sets the laser current limit using the GPIB command.
    """
    try:
        # Ensure the current limit is in amperes
        command = f"LAS:LDI?"
        send_command(instrument, command)

        # Verify the current limit was set correctly
        response = query_device(instrument, "LAS:LDI?")
        print(f"Laser current limit confirmed: {response.strip()} mA")
        return response
    except Exception as e:
        print(f"Error setting laser current limit: {e}")

# def main():
#     """
#     Main function to control the device.
#     """
#     # Initialize the device
#     instrument = initialize_device()
#     if not instrument:
#         return

#     # Example SCPI commands
#     send_command(instrument, "*RST")  # Reset the device
#     query_device(instrument, "*IDN?")  # Query device identification

#     # Set laser current limit to 168 mA (0.168 A)
#     set_laser_current(instrument, 10)
#     get_laser_current(instrument)
#     # Close the connection
#     instrument.close()

# if __name__ == "__main__":
#     main()