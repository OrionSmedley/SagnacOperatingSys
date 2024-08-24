#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2017 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import truncated_discrete_set, truncated_range, modular_range, modular_range_bidirectional, strict_discrete_set

from time import sleep
import numpy as np


class PSPL10070A(Instrument):
    """This is the class for the DSP 7265 lockin amplifier"""
    # TODO: add regultors on most of these

    amplitude = Instrument.control(
        "amplitude?", "amplitude %g",
        """ A floating point property that represents the voltage
        in Volts. This property can be set. """,
        validator=truncated_range,
        values=[0,5]
    )

    x = Instrument.measurement("X.",
        """ Reads the X value in Volts """
    )
    
    id = Instrument.measurement("ID",
        """ Reads the instrument identification """
    )

    def __init__(self, resourceName, **kwargs):
        super(PSPL10070A, self).__init__(
            resourceName,
            "Picosecond Pulse Labs 10070A",
            **kwargs
        )

        # Pre-condition
        # self.adapter.config(datatype = 'str', converter = 's')


    def shutdown(self):
        log.info("Shutting down %s." % self.name)
        self.voltage = 0.
        # self.isShutdown = True
