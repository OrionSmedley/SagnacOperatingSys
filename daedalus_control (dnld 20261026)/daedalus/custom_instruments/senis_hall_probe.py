import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.instruments import Instrument
try:
    import nidaqmx as daqmx
    from nidaqmx.stream_readers import AnalogSingleChannelReader, AnalogMultiChannelReader
except:
    pass

import numpy as np

class senis3AxHallProbe:
    """
    Basic implementatoin of the senis 3 axis Hall probe attached to the
    Daedalus setup. Includes all necessary conversions. Note the strange
    coordinate system.
    """

    volt2tesla = 0.2
    rad2deg = 180./np.pi
    deg2rad = np.pi/180.

    @property
    def x_field(self):
        return self.read_single_voltage(self.dev_x)*self.volt2tesla

    @property
    def y_field(self):
        return self.read_single_voltage(self.dev_y)*self.volt2tesla

    @property
    def z_field(self):
        return -1*self.read_single_voltage(self.dev_z)*self.volt2tesla

    @property
    def polar_field(self):
        # positive y is down, positive z is forward, positive x is right
        x, y, z = self.field
        phi = self.rad2deg*np.arctan2(y,x)
        theta = 90.-self.rad2deg*np.arctan2(np.sqrt(x**2+y**2),z)
        r = np.sqrt(x**2+y**2+z**2)
        return np.array([r,phi,theta])

    @property
    def field(self):
        volts = self.read_all_voltages()
        volts[2] *= -1
        return self.read_all_voltages()*self.volt2tesla

    def __init__(self, adapter):
        # expects a DAQmxAdapter class with three channels, [x, y, z] channels
        self.dev_x = '/' + adapter.resource_name + '/' + adapter.channels[0]
        self.dev_y = '/' + adapter.resource_name + '/' + adapter.channels[1]
        self.dev_z = '/' + adapter.resource_name + '/' + adapter.channels[2]
        self.volt2tesla = 0.2

    def read_single_voltage(self, device):
        """
        Reads 1000 points from the device and returns the average of them.
        Sampling should happen super fast.
        """
        with daqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(device, min_val=-10., max_val=10.)
            
            stream = AnalogSingleChannelReader(task.in_stream)
            data = np.empty(1_000)
            
            stream.read_many_sample(data, number_of_samples_per_channel=data.shape[-1])
            
            return data.mean()
    
    def read_all_voltages(self):
        """
        Reads 1000 points from the device and returns the average of them.
        Sampling should happen super fast.
        """
        with daqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(self.dev_x, min_val=-10., max_val=10.)
            task.ai_channels.add_ai_voltage_chan(self.dev_y, min_val=-10., max_val=10.)
            task.ai_channels.add_ai_voltage_chan(self.dev_z, min_val=-10., max_val=10.)
            
            stream = AnalogMultiChannelReader(task.in_stream)
            data = np.empty((3,1_000))
            
            stream.read_many_sample(data, number_of_samples_per_channel=data.shape[-1])
            
            return data.mean(axis=-1)
