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
from pymeasure.instruments.validators import truncated_range

def handle_timeout(fail_mode):
    def handle_timeout_decorator(func):
        def func_wrapper(self, *args, **kwargs):
            esp_faliure_counter = 0
            esp_success = False
            FALIURE_LIMIT = 10
            while esp_faliure_counter < FALIURE_LIMIT:
                try:
                    return func(self, *args, **kwargs)
                except pyvisa.errors.VisaIOError:
                    esp_faliure_counter += 1
                    log.warning("failed {mode}, at count {count} of {max}".format(
                        mode=fail_mode,
                        count=esp_faliure_counter,
                        max=FALIURE_LIMIT
                        )
                    )
                    log.info("Clearing GPIB connection %s"%self.name)
                    self.adapter.manager.visalib.clear(self.adapter.connection.session)
                    continue
                esp_success = True # only runs if we beat try statement
                break
            if not esp_success:
                raise RuntimeError("Not able to successfully communicate with ESP300")
        return func_wrapper
    return handle_timeout_decorator


class AMI420(Instrument):
    """
    Represents the AMI Model 420 magnet power supply
    """
    ERRORS = {
        "No errors": 0,
        'Unrecognized Command': -101,
        'Invalid Argument': -102,
        "Non-boolean argument": -103,
        "Missing Parameter": -104,
        "Out of Range": -105,
        "Undefined coil const": -106,
        "No switch installed": -107,
        "Unrecognized query": -201,
        "Undefined coil const": -202,
        "Query interrupted": -203,
        "Heating Switch": -301,
        "Quench condition": -302,
        "Input overflow": -303,
        "Error buffer overflow": -304,
        "Checksum failed": -401,
        "Serial framing error": -402,
        "Serial parity error": -403,
        "Serial data overrun": -404
    }

    error = Instrument.measurement(
        ":SYSTem:ERRor?",
        """Reads the most recent error reported by the instrument""",
        values=ERRORS,
        map_values=True
    )

    def clear_errors(self):
        """
        Clears all errors and returns a list of accumulated errors
        """
        errors = [self.error]

        while errors[-1] != ERRORS[0]:
            errors.append(self.error)

        return errors

    STATES = [
        'Dummy', # There should never be a 0 index returned
        'Ramping',# to programmed current/field
        'Holding', # to programmed current/field
        'Paused',
        'Ramping in manual up mode',
        'Ramping in manual down mode',
        'Zeroing', # current
        'Quench', #detected
        'Heating persistent switch'
        ]
    state = Instrument.measurement(
        "STATE?", """Returns the state of the power supply""",
        values=STATES,
        map_values=True
    )

    ######################
    ### SETUP COMMANDS ###
    ######################
    @handle_timeout("setting local")
    def local(self):
        """
        Sets the status to local, enabling front panel controls
        """
        self.write("SYSTem:LOCal")

    @handle_timeout("setting remote")
    def remote(self):
        """
        Sets the status to remote, disabling front panel controls
        """
        self.write("SYSTem:REMote")

    @handle_timeout("setting current to zero")
    def set_zero(self):
        """
        Sets the current to ZERO
        """
        self.write("ZERO")

    def set_ramp_mode(self):
        """
        Sets the current to ZERO
        """
        self.write("RAMP")



    current_minimum = Instrument.control(
        "CURRent:MINimum?", "CONFigure:CURRent:MINimum %g",
        """ A floating point property setting the minimum current output of the
        power supply in Amps """,
        validator=truncated_range,
        values = [-100, 100]
    )

    current_maximum = Instrument.control(
        "CURRent:MAXimum?", "CONFigure:CURRent:MAXimum %g",
        """ A floating point property setting the maximum current output of the
        power supply in Amps """,
        validator=truncated_range,
        values = [-100, 100]
    )

    voltage_minimum = Instrument.control(
        "VOLTage:MINimum?", "CONFigure:VOLTage:MINimum %g",
        """ A floating point property setting the minimum compliance voltage of
        the power supply in Volts """,
        validator=truncated_range,
        values = [-5, 5]
    )

    voltage_maximum = Instrument.control(
        "VOLTage:MAXimum?", "CONFigure:VOLTage:MAXimum %g",
        """ A floating point property setting the maximum compliance voltage of
        the power supply in Volts """,
        validator=truncated_range,
        values = [-5, 5]
    )

    stability = Instrument.control(
        "STABility?", "CONFigure:STABility %f",
        """ A floating point property setting the stability in percent """,
        validator=truncated_range,
        values = [0, 100]
    )

    coil_constant = Instrument.control(
        "COILconst?", "CONFigure:COILconst %g",
        """ A floating point quantity setting the coil constant
        (field-to-current ratio) for the magnet being controlled """,
        validator=truncated_range,
        values=[0,99999999999]
    )

    magnet_current_limit = Instrument.control(
        "CURRent:LIMit?", "CONFigure:CURRent:LIMit %g",
        """ A floating point quantity which sets a limit on the amount of
        current supplied to the magnet in Amps """,
        validator=truncated_range,
        values=[0, 100] # TODO: Use manual to come up with a reasonable value
    )

    auto_quench_detect = Instrument.control(
        "QUench:DETect?", "CONFigure:QUench:DETect %d",
        """ Boolean value enabling or disabling automatic magnet quench
        detection """,
        cast=bool
    )

    field_units = Instrument.control(
        "FIELD:UNITS?", "CONFigure:FIELD:UNITS %d",
        """ Controls whether field units are in kG or T """,
        values=['kilogaus', 'tesla'],
        map_values=True
    )

    ramp_rate_units = Instrument.control(
        "RAMP:RATE:UNITS?", "CONFigure:RAMP:RATE:UNITS %d",
        """ Controls whether rate rate is in seconds or minutes """,
        values=['seconds', 'minutes'],
        map_values=True
    )


    ###############
    ### RAMPING ###
    ###############

    voltage_ramp_limit = Instrument.control(
        "VOLTage:LIMit?", "CONFigure:VOLTage:LIMit %g",
        """ A floating point value setting the voltage limit during a ramp """,
        validator=truncated_range,
        values=[0, 5]
    )

    # TODO: 2 possiblities for units, how to set validator properly??
    current_ramp_rate = Instrument.control(
        "RAMP:RATE:CURRent?", "CONFigure:RAMP:RATE:CURRENT %g",
        """A floating point value setting the current ramp rate. """,
        validator=truncated_range,
        values=[1.66e-5, 10] # in A/s
    )

    # TODO: 2 possiblities for units, how to set validator properly??
    current_setpoint = Instrument.control(
        "CURRent:PROGram?", "CONFigure:CURRent:PROgram %g",
        """ A floating point value controlling the current setpoint """,
        validator=truncated_range,
        values=[-100,100]
    )

    # TODO: 4 possiblities for units, how to set validator properly??
    field_ramp_rate = Instrument.control(
        "RAMP:RATE:FIELD?", "CONFigure:RAMP:RATE:FIELD %g",
        """A floating point value setting the field ramp rate, assuming a
        coil constant is defined """,
        validator=truncated_range,
        values=[1.66e-5, 10] # totally depends
    )

    # TODO: 2 possiblities for units, how to set validator properly??
    field_setpoint = Instrument.control(
        "FIELD:PROGram?", "CONFigure:FIELD:PROgram %g",
        """ A floating point value controlling the field setpoint, assuming a
        coil constant is defined """,
        validator=truncated_range,
        values=[-7,7] # totally depends, in T
    )

    ###############
    ### READING ###
    ###############

    magnet_voltage = Instrument.measurement(
        "VOLTage:MAGnet?", """Reads the magnet voltage in volts"""
    )

    magnet_current = Instrument.measurement(
        "CURRent:MAGnet?", """Reads the magnet current in Amps"""
    )

    magnet_field = Instrument.measurement(
        "FIELD:MAGnet?", """Reads the magnet field in kG or T, depending on
        the set units, assuming a coil constant is set. """
    )

    voltage_supply = Instrument.measurement(
        "VOLTage:SUPPly?", """Reads the total voltage used by the power supply"""
    )

    def __init__(self, resourceName, **kwargs):
        super().__init__(
            resourceName,
            "AMI 420 Magnet Power Supply",
            **kwargs
        )

    def shutdown(self):
        super().shutdown()
        self.write('ZERO') # turn current off
