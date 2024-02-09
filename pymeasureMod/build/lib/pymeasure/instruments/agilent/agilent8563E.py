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

from pymeasure.instruments import Instrument

import numpy as np
import re
from io import StringIO
#import struct for unpacking binary data, if we need


class Agilent8563E(Instrument):
    """ Represents the Agilent8563E Spectrum Analyzer and
    allows interfacing to take spectrum traces
    """
    trace_length = 601 #unchangeable trace length of instrument

    center_frequency = Instrument.control(
        "CF?", "CF %d Hz",
        """ An integer property to set the center frequency
        """
    )

    span = Instrument.control(
        "SP?", "SP %d Hz",
        """ An integer property to set the span
        """
    )

    start_frequency = Instrument.control(
        "FA?", "FA %d Hz",
        """ An integer property to set the start frequency
        """
    )
    stop_frequency = Instrument.control(
        "FB?", "FB %d Hz",
        """ An integer property to set the stop frequency
        """
    )
    reference_level = Instrument.control(
        "RL?", "RL %f DBM",
        """ A float property to set the reference_level
        """
    )
    resolution_bandwidth = Instrument.control(
        "RB?", "RB %d Hz",
        """ An integer property to set the resolution_bandwidth
        """
    )
    video_bandwidth = Instrument.control(
        "VB?", "VB %d Hz",
        """ An integer property to set the video_bandwidth
        """
    )
    sweep_time = Instrument.control(
        "ST?", "ST %d SEC",
        """ An integer property to set the sweep_time
        """
    )

    def __init__(self, resourceName, **kwargs):
        super(Agilent8563E, self).__init__(
            resourceName,
            "Agilent 8563E Spectrum Analyzer",
            **kwargs
        )

    @property
    def log_scale(self):
        """ ask if it is a log_scale
        """
        return self.ask("LG?;")
    @log_scale.setter
    def log_scale(self, Lg):
        """ set the log_scale
        """
        available_scales = [1,2,5,10] #dB
        if Lg == 0:
            self.write("LN;") #linear scale
        else:
            self.write("LG %d dB;" %Lg) # 1, 2, 5, or 10 dB/div

    def get_settings(self):
        """ returns all of the settings
        """
        return {"start_frequency": self.start_frequency,
                "stop_frequency": self.stop_frequency,
                "reference_level": self.reference_level,
                "resolution_bandwidth": self.resolution_bandwidth,
                "video_bandwidth": self.video_bandwidth,
                "sweep_time": self.sweep_time,
                "log_scale": self.log_scale,
                "aunits": self.aunits,
        }

    def set_settings(self,Fa,Fb,Rl,Rb,Vb,St,Lg):#,Aunits):
        self.start_frequency = Fa
        self.stop_frequency = Fb
        self.reference_level = Rl
        self.resolution_bandwidth = Rb
        self.video_bandwidth = Vb
        self.sweep_time = St
        self.log_scale = Lg
        #self.aunits TODO: user control


    def default_config(self,Rb,Vb):
        self.write("IP")
        self.resolution_bandwidth = Rb
        self.video_bandwidth = Vb
        self.reference_level = 0
    def zero_span_scan(self,Cf):
        """
        Zero span scan can give an Amplitude vs. Time Measurement
        """
        self.center_frequency = Cf
        self.reference_level = 0
        self.span = 0
        self.write("SNGLS; TS;") #single sweep; take sweep;
        self.write("TDF P;") # measurement in the same units as parameters,
        #                      will be same as AUNITS
        A = self.ask("TRA?;") # stores trace A
        return np.mean(np.array(A.rstrip().split(',')).astype(float))

    def scan(self,Cf, Sp):
        """
        scan that allows you to set the center frequency, span and sweep time
        """
        self.center_frequency=Cf
        self.span = Sp
        self.reference_level=0
        self.write("SNGLS; TS;") #single sweep; take sweep;
        self.write("TDF P;") # measurement in the same units as parameters,
        #                      will be same as AUNITS
        A = self.ask("TRA?;") # stores trace A
        return np.array(A.rstrip().split(',')).astype(float)

    def fixed_window(self, Fa, Fb, Rb, Vb):
        """
        fixes the scan window, good for a frequency sweep
        """
        self.default_config(Rb,Vb)
        self.start_frequency = Fa
        self.stop_frequency = Fb
        #self.write('AUNITS DBM')

    def fixed_scan(self):
        """
        sweep on a fixed window
        """
        self.write("SNGLS; TS;")
        self.write("TDF P;")
        A = self.ask("TRA?;")
        return np.array(A.rstrip().split(',')).astype(float)
