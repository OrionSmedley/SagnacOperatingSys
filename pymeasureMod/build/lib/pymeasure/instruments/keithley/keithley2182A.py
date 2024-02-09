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

from time import sleep
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import (
    truncated_range, truncated_discrete_set,
    strict_discrete_set
)
from pymeasure.adapters import VISAAdapter

class Keithley2182A(Instrument):
    """ Represents the Keithley 2182A nanovoltmeter and provides a high-level
    interface for interacting with the instrument.
    """

    SENSE_MODES = {
        'temperature': "TEMP",
        'voltage': "VOLT"
    }

    SENSE_CHANNELS = ['internal', 1, 2] # QUESTION: is this useful?

    VOLTAGE_RANGES = [10e-3, 100e-3, 1, 10, 100]

    ## Setup and calibration

    def set_voltage_mode(self):
        """ Sets the instrument into voltage mode """
        self.write(":SENS:FUNC VOLT")

    def set_temperature_mode(self):
        """ Sets the instrument into temperature mode """
        self.write(":SENS:FUNC TEMP")

    channel = Instrument.control(
        "SENS:CHAN?", ":SENS:CHAN %d",
        """ Parameter controlling the channel used for reading """ # TODO: validators and such? mapped values?
    )

    def calibrate_low_level(self):
        self.write(":CAL:UNPR:ACAL:INIT")
        self.write(":CAL:UNPR:ACAL:STEP2")
        self.write(":CAL:UNPR:ACAL:DONE")

    def calibration_is_good(self):
        """ Determines if the calibration is good, i.e. if the internal temperature
        is within 1 C of the last calibration """
        self.temperature_unit = "C"
        old_temp = self.values(":CAL:UNPR:ACAL:TEMP?")[0]
        self.channel = 0
        self.set_temperature_mode()
        current_temp = self.temperature
        return 1

    # measurements

    # QUESTION: Should we have the measurements done in "one-shot" mode
    # as in Ch. 13 of the manual?

    ## voltage

    voltage = Instrument.measurement(
        ":SENS:DATA:FRES?",
        """ Reads a fresh measurement from the instrument. Depends on instrument
        being in the correct mode. """
    )

    # TODO: change to control? can probably query this
    voltage_range = Instrument.setting(
        ":SENS:VOLT:RANG %f",
        """ Sets the voltage range of the instrument. Should pass expected
        maximum voltage readings """
    )

    # TODO: change to control? can probably query this
    rate = Instrument.setting(
        ":SENS:VOLT:NPLC %f",
        """ Sets the instruments measuring rate in number of power line cycles.
        Best sensitivity between 1-5 PLC. """,
        validator=truncated_range,
        values=[0.01,60.]
    )

    def enable_low_pass_filter(self):
        """ Enables analog low-pass filter """
        self.write(":SENS:VOLT:LPAS ON")

    def disable_low_pass_filter(self):
        """ Disables analog low-pass filter """
        self.write(":SENS:VOLT:LPAS OFF")

    def configure_digital_filter(self, window, count=10, type='repeating'):
        """
        Configures the digital filter

        :param window: A floating point percentage of the current range specifying
        the values to accept while filtering.
        :param count: An integer defining the number of data points to take in
        the filter.
        :param type: A string defining the type of filtering to do.
        """

        good_window = truncated_range(window, [0, 10])
        good_count = truncated_discrete_set(count, range(1,101))

        self.write(":SENS:VOLT:DFIL:STAT ON")
        self.write(":SENS:VOLT:DFIL:WIND %f" % good_window)
        self.write(":SENS:VOLT:DFIL:COUN %d" % good_count)
        if type == 'repeating':
            self.write(":SENS:VOLT:DFIL:TCON REP")
        elif type == 'moving':
            self.write(":SENS:VOLT:DFIL:TCON MOV")
        else:
            raise ValueError("Bad digital filter type! Must be 'repeating' or 'moving'")
        self.write(":SENS:VOLT:DFIL:STAT ON")

    def disable_digital_filter(self):
        """ Disables the digital filter """
        self.write(":SENS:VOLT:DFIL:STAT OFF")

    ## temperature

    # TODO: setting thermocouples, rates, ranges etc.

    temperature = Instrument.measurement(
        ":SENS:DATA:FRES?",
        """ Reads a fresh measurement from the instrument. Depends on instrument
        being in the correct mode. """
    )

    # TODO: change to control? can probably query this
    temperature_unit = Instrument.setting(
        ":UNIT:TEMP %s",
        """ Selects unit used for temperature. Should be "K", "C" or "F". """
    )

    # TODO: analog output

    def __init__(self, adapter, **kwargs):
        super().__init__(
            adapter, "Keithley 2182A nanovoltmeter", **kwargs
        )
        # # Set up data transfer format
        # if isinstance(self.adapter, VISAAdapter):
        #     self.adapter.config(
        #         is_binary=False,
        #         datatype='float32',
        #         converter='f',
        #         separator=','
        #     )
