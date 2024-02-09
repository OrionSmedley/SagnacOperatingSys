import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.instruments import Instrument
import thorlabs_apt as apt
import thorlabs_apt.core as apt_core
from pymeasure.instruments.validators import modular_range, modular_range_bidirectional

class ThorlabsTDC001(Instrument): # NOTE: Now more about the device than controller...
    """This is the class for a Thorlabs TDC 001 motor controller """

    def setposition(self, nposition):
        value = modular_range(nposition,[0,365.])
        log.info("Changing position to %f" % value)
        self.motor.move_to(value)
        log.info("Successfully changed to %f" % value)

    def getposition(self):
        return self.motor.position

    position = property(getposition,setposition)

    @property
    def is_in_motion(self):
        return self.motor.is_in_motion

    def __init__(self, resourceName, **kwargs):
        super(ThorlabsTDC001, self).__init__(
            resourceName,
            "Thorlabs TDC 001 motor conroller",
            **kwargs
        )
        try:
            log.info("Attempting to connect motor %d"%self.adapter.serial)
            self.motor = apt.Motor(self.adapter.serial)
        except:
            log.error("Unable to find Thorlabs APT motor with serial number %d" % self.adapter.serial)
            apt_core._cleanup()

    def move_relative(self, delta):
        value = modular_range_bidirectional(delta,[-365.,365.])
        self.motor.move_by(value)

    def shutdown(self):
        """ ensures motor is stopped and communications are
        broken appropriately.
        """
        log.info("Shutting down %s." % self.name)
        self.motor.stop_profiled()
        apt_core._cleanup()
        self.isShutdown = True
