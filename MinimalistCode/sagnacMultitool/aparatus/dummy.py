import numpy as np

class Instrument:
    def __init__(self):
        self.phase = 0
        self.frequency = 0
        self.temperature = 0
        self.junk = 100

    def get_voltage(self):
        # Simulate voltage based on current settings
        return self.frequency * np.cos(self.phase) + self.temperature / 10

    @property
    def current(self):
        # Simulate current based on current settings
        return self.frequency * np.sin(self.phase) + self.temperature / 20
    
    def set_junk(self, value):
        self.junk = value
        

# Create a global instance of the instrument
instrument = Instrument()

# # Export only the instance
# __all__ = ["instrument"]
