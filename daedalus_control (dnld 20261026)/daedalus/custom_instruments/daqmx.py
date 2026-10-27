import logging

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class DAQmxAdapter(object):
    """
    Dummy DAQmx adapter class.
    Stores device number and channel number(s)
    """

    def __init__(self, device_num, channels):
        self.resource_name = device_num
        if isinstance(channels,str):
            self.channels = []
            self.channels.append(channels)
        else:
            try:
                self.channels = list(channels)
            except TypeError:
                log.error("Bad channels given to DAQmx")
                self.chanels = None
