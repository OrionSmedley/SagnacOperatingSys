from time import sleep
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa

class APS100(Instrument):
    """ Represents a Attocube APS100 programmable magnet power supply """

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            "Keithley 220 Programmable Current Source",
            **kwargs
        )

    current = Instrument.control(
        "IMAG?", "IMAG %g",
        """ A floating point property that represents the current
        in Amps. This property can be set. """,
        validator=truncated_range,
        values=[-1,1]
    )

    def shutdown(self):
        """ Sets current to zero and disables the instrument """
        super().shutdown()
        self.current = 0.
        self.disable()

