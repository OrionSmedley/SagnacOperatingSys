import logging

import thorlabs_apt

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class ThorlabsAPTAdapter(object):
    """
    Dummy thorlabs APT adapter class.
    Stores the serial address of the device.
    """

    def __init__(self, serial_no):
        self.serial = serial_no
