import pyvisa

class LaserDriver:
    """
    Minimal driver for controlling a laser via GPIB using pyvisa.
    
    Example usage:
        driver = LaserDriver(gpib_address="GPIB0::2::INSTR")
        print(driver.get_idn())
        driver.set_ld_current(148)
        print(driver.get_ld_current())
        driver.set_temperature(21.5)
        print(driver.get_temperature())
    """
    
    def __init__(self, gpib_address="GPIB0::2::INSTR"):
        """
        Initialize the LaserDriver by opening a connection to the specified GPIB address.
        """
        self._resource_manager = pyvisa.ResourceManager()
        self._laser = self._resource_manager.open_resource(gpib_address)

    def get_idn(self):
        """
        Query and return the instrument identification string.
        """
        return self._laser.query("*IDN?").strip()

    def set_ld_current(self, current):
        """
        Set the laser diode current (LDI) to a specified value in mA.
        :param current: (float) The desired current value, e.g. 148.
        """
        self._laser.write(f":LAS:LDI {current}")

    def get_ld_current(self):
        """
        Query and return the current laser diode current (LDI) setting.
        :return: (str) The current value as a string.
        """
        return self._laser.query(":LAS:LDI?").strip()
    
    def set_ldv(self, V):
        """
        Set the laser diode current (LDv) to a specified value in mA.
        :param current: (float) The desired current value, e.g. 148.
        """
        self._laser.write(f":LAS:LDV {V}")

    def get_ldv(self):
        """
        Query and return the current laser diode current (LDv) setting.
        :return: (str) The current value as a string.
        """
        return self._laser.query(":LAS:LDV?").strip()

    def set_temperature(self, temperature):
        """
        Set the temperature (TEC:T) to a specified value.
        :param temperature: (float) The desired temperature value, e.g. 21.5.
        """
        self._laser.write(f":TEC:T {temperature}")

    def get_temperature(self):
        """
        Query and return the current temperature (TEC:T) setting.
        :return: (str) The current temperature as a string.
        """
        return self._laser.query(":TEC:T?").strip()

    def close(self):
        """
        Close the connection to the instrument.
        """
        self._laser.close()

    # Properties
    LDI = property(get_ld_current, set_ld_current)
    T = property(get_temperature, set_temperature)
    LDV = property(get_ldv, set_ldv)

# Example usage:
if __name__ == "__main__":
    driver = LaserDriver("GPIB0::2::INSTR")
    
    # Check device info
    print("Instrument ID:", driver.get_idn())
    
    # Set and query LD current
    print("LD Current:", driver.get_ld_current())
    
    # Set and query temperature
    print("Temperature:", driver.get_temperature())
    
    # Close the connection
    driver.close()
