import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import truncated_range

import numpy as np

class Keithley220(Instrument):
    """ Represents a Keithley 220 programmable current source """

    current = Instrument.setting(
        "I%gX", """ Sets the current in Amps """,
        validator = truncated_range,
        values = [-0.101,0.101]
        )

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            "Keithley 220 Programmable Current Source",
            **kwargs
        )

    def enable(self):
        """ Enables output """
        self.write('F1X')

    def disable(self):
        """ Disables output """
        self.write('F0X')

    def shutdown(self):
        """ Sets current to zero and disables the instrument """
        super().shutdown()
        self.current = 0.
        self.disable()
