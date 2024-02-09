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

from pymeasure.instruments import Instrument, RangeException
from pymeasure.adapters import PrologixAdapter
from pymeasure.instruments.validators import truncated_range, strict_discrete_set

from .buffer import KeithleyBuffer

import numpy as np
import time
from io import BytesIO
import re


class Keithley6221(Instrument, KeithleyBuffer):
    """ Represents the Keithely 6201 SourceMeter and provides a
    high-level interface for interacting with the instrument.
    """

    wave_amp = Instrument.control(
        ":SOUR:WAVE:AMPL?", ":SOUR:WAVE:AMPL %g",
        """ A float property that controls the Wave amplitude """,
        validator=truncated_range,
        values=[2e-12, 105e-3]
    )

    wave_freq = Instrument.control(
        ":SOUR:WAVE:FREQ?", ":SOUR:WAVE:FREQ %g",
        """ A float property that controls the Wave frequency """,
        validator=truncated_range,
        values=[1e-3, 1e5]
    ) 

    wave_offset = Instrument.control(
        ":SOUR:WAVE:OFFS?", ":SOUR:WAVE:OFFS %g",
        """ A float property that controls the Wave offset""",
        validator=truncated_range,
        values=[-105e-3, 105e-3]
    )

    marker_phase = Instrument.control(
        ":SOUR:WAVE:PMAR:LEV?", ":SOUR:WAVE:PMAR:LEV %g",
        """ A float property that controls the Phase Marker
            phase in degrees""",
        validator=truncated_range,
        values=[0, 360]
    )

    marker_line = Instrument.control(
        ":SOUR:WAVE:PMAR:OLIN?", ":SOUR:WAVE:PMAR:OLIN %d",
        """ An integer property that controls the Phase Marker
            output line""",
        validator=truncated_range,
        values=[1, 6]
    )


    def __init__(self, adapter, **kwargs):
        super(Keithley6221, self).__init__(
            adapter, "Keithley 6221 SourceMeter", **kwargs
        )

    def set_wave_mode(self):
        self.write(":SOUR:WAVE:SIN")
    
    def set_wave_amplitude(self, amp):
        self.wave_amp = amp

    def set_wave_frequency(self, f):
        self.wave_freq = f

    def set_wave_offset(self, off):
        self.wave_offset = off
    
    def enable_phase_marker(self):
        self.marker_phase = 180
        self.marker_line = 1
        self.write(":SOUR:WAVE:PMAR:STAT ON")

    def disable_phase_marker(self):
        self.write(":SOUR:WAVE:PMAR:STAT OFF")

    def arm_wave(self):
        self.write(":SOUR:WAVE:ARM")
    
    def start_wave(self):
        self.write(":SOUR:WAVE:INIT")

    def stop_wave(self):
        self.write(":SOUR:WAVE:ABOR")

    def shutdown(self):
        """ Ensures that the current or voltage is turned to zero
        and disables the output. """
        log.info("Shutting down %s." % self.name)
        self.stop_wave()
