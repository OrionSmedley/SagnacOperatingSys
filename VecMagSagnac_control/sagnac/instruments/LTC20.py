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
from pymeasure.instruments.validators import truncated_range, truncated_discrete_set, strict_discrete_set

class LTC20(Instrument):
    """
    Represents the Conductus LTC-20 temperature controller
    """

    # TODO: For everything using QOUT?1 not sure if these things are
    # *bytes* 0, 1, 2, etc. or if they are the actual ASCII characters for
    # 0, 1, 2, etc. if the latter, don't need ord

    # TODO: deal with errors somehow

    READ_MODES = ['monitor', 'control', 'autotune', 'off']

    def get_mode(self):
        imode = self.ask("QISTATE?")
        return self.READ_MODES[int(imode[:-1])]

    WRITE_MODES = {
        'control': "SCONT",
        'monitor': "SMON"
    }

    def set_mode(self, mode):
        """
        Sets the mode of the instrument
        """
        self.write(self.WRITE_MODES[mode])

    mode = property(get_mode, set_mode)

    STATE={
    'Temperature control is in MONITOR mode': 0,
    'Controller is in CONTROL mode': 1,
    'Autotune is in progress' : 2,
    'Controller is in OFF mode (no temperature display)' : 3
    }

    instrument_state = Instrument.measurement(
    "QISTATE?",
    """Queries the instrument state""",
    get_process = lambda x: int(x[:-1]),
    values=STATE,
    map_values=True
    )
    ####################
    # Sensor Selection #
    ####################

    SENSOR_TYPES = {
        "LS Diode #10": 1,
        "CryoCal D3": 2,
        "SI-410NN": 3,
        "LS TG-120": 4,
        "PT100-385": 5,
        "PT1000-385": 6,
        "PT100-392": 7,
        "PT1000-392": 8,
        "234567": 20,
        "7777777": 17
    }

    SENSORS = {
    "Should never happen": 0 ,
    "Sensor #1": 1,
    "Sensor #2": 2,
    "None": 3
    }

    sensor1_set_type = Instrument.setting(
        "SSTYPE 1, %s",
        """Controls type of sensor connected to sensor 1""",
        values=SENSOR_TYPES,
        map_values=True
    )

    sensor1_get_type = Instrument.measurement(
        "QSTYPE?1",
        """Inquires the type of sensor connected to sensor 1""",
        get_process=lambda x: x[:-1]
    )


    sensor2_set_type = Instrument.setting(
        "SSTYPE 2, %d",
        """Controls type of sensor connected to sensor 2""",
        values=SENSOR_TYPES,
        map_values=True
    )

    sensor2_get_type = Instrument.measurement(
        "QSTYPE?2",
        """Inquires the type of sensor connected to sensor 2""",
        get_process=lambda x: x[:-1]
    )


    heater_sensor = Instrument.control(
        "QOUT?1", "SOSEN 1, %d",
        """Controls which sensor is connected to the heater""",
        get_process=lambda x: int(x[0]), # should work, returns three bytes. First one represents the sensor
        validator=strict_discrete_set,
        values=SENSORS,
        map_values=True
    )

    UNITS = {
        "kelvin": 'K',
        "celsius": 'C',
        "fahrenheit":'F',
        "no sensor": 'N',
        "volts":'V',
        "ohms": 'O'
    }

    sensor1_set_unit = Instrument.control(
        "QUNIT?1", "SUNIT?1, %s",
        """Controls the units assinged to sensor channel 1 """,
        get_process = lambda x: x[:-1],
        values=UNITS,
        map_values=True
    )

    sensor1_read_temp = Instrument.measurement(
        "QSAMP?1",
        """Requests the temperature measured by sensor 1 """,
        get_process=lambda x: float(x[:-2]) #Excluding last character
        #First 10 ASCII characters contain the measurement, 11th character contains the unit
    )

    sensor2_set_unit = Instrument.control(
        "QUNIT?2", "SUNIT?2, %s",
        """Controls the units assinged to sensor channel 2 """,
        get_process = lambda x: x[:-1],
        values=UNITS,
        map_values=True
    )

    sensor2_read_temp = Instrument.measurement(
        "QSAMP?2",
        """Requests the temperature measured by sensor 2 """,
        get_process=lambda x: float(x[:-2]) #Excluding last character
        #First 10 ASCII characters contain the measurement, 11th character contains the unit
    )

    ##################
    # Heater Control #
    ##################

    RANGES = ['off','low','medium','high','maximum']

    heater_range = Instrument.control(
        "QOUT?1", "SHMXPWR %d",
        """Sets maximum heater power to specified range""",
        get_process=lambda x: int(x[4]),
        values=RANGES,
        map_values=True,
         # should work, returns three bytes and last one contains information on heater range
    )

    heater_power = Instrument.measurement(
        "QHEAT?",
        """Reads percent of full heater output in current range""",
        get_process=lambda x: float(x[:-1])
    )

    heater_setpoint = Instrument.control(
        "QSETP?1", "SETP 1, %g",
        """Floating point property controlling the heater setpoint""",
        get_process=lambda x: float(x[:-2]) # TODO: will need something, need to determine that
    )

    HEATER_MODES = ['auto P', 'auto PI', 'auto PID', 'manual', 'table', 'default']

    heater_control_mode = Instrument.control(
        "QOUT?1", "SHCONT %d",
        """ Sets heater control mode to manual or various auto options """,
        values=HEATER_MODES,
        map_values=True,
        get_process=lambda x: int(x[2]) # should work, returns three bytes and second one contains information on heater control mode
    )



    ##################
    # PID and Tuning #
    ##################

    heater_PID = Instrument.measurement(
        "QPID?1",
        """ Returns the heater PID settings values """,
    )

    tune_state = Instrument.setting(
        "STUNE %d",
        """ Sets tune state""",
        values=['manual','auto'],
        map_values=True
    )

    TUNE_SPEEDS = {
        'fast': 'F',
        'normal': 'N',
        'slow': 'S'
    }

    tune_response_speed = Instrument.control(
        "QTUNEP?1", "STUNEP 1, %s",
        """ Controls the assumed system response speed to help autotuning """,
        get_process=lambda x: x[:-1],
        values=TUNE_SPEEDS,
        map_values=True
    )

    tune_deviation = Instrument.control(
        "QTUNEP?2", "STUNEP 2, %f",
        """ Controls the percentage temperature setpoint change when the system
        should automatically retune if in autotune mode, in percent""",
        values=[0,50],
        validator=truncated_range,
        get_process=lambda x: float(x[:-2]) # for some reason, writes in percent but reads in fraction...
    )

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            "LTC-20 Temperature Controller",
            write_termination=";", # checked in LTC manual, but may not work based on Pymeasure implementation of VISA adapter
            separator=',',
            read_termination='\n', #works
            **kwargs
        )

    def lock(self):
        """
        Locks the front panel buttons of the instrument
        """
        self.write("SLLOCK1")

    def set_heater_PID(self, P, I , D, pct=0):
        """ Sets heater PID values and ensures they are valid """

        goodP = truncated_discrete_set(P,list(range(1,1001)))
        goodI = truncated_discrete_set(I,list(range(1,1001)))
        goodD = truncated_discrete_set(D,list(range(1,goodI//2+1)))
        goodPct = truncated_discrete_set(pct,list(range(0,101))) # constant power to output regardless of PID. Should only be used alone (PID=0)
        self.write("SPID 1, %d, %d, %d, %d"%(goodP,goodI,goodD,goodPct))

    def shutdown(self):
        super().shutdown()
