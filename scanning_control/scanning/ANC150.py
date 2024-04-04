from pymeasure.instruments import Instrument

from .ANC150adapters import ANC150Adapter
# import adapter file



class ANC150(Instrument):

    def __init__(self, port):

        adapter = ANC150Adapter(port)

        # super(ANC150, self).__init__(
        #     ANC150Adapter(port),
        #     "ANC150 Piezo controller",
        # )


        super(ANC150, self).__init__(
             adapter,
            "ANC150 Piezo controller",
        )

        #self.axis = str(axis)

    
    # pattern_upward = Instrument.measurement(
    #     "getpu " + self.axis, 
    #     """ Returns pattern number for upward movement on axis <AID>
    #     """
    # )
    
    # pattern_downward = Instrument.measurement(
    #     "getpd " + self.axis, 
    #     """ Rerturns pattern number for dwonward movement on axis <AID>
    #     """
    # )
    
    
    # #value_index = Instrument.control(
    #     #"getp" + str(pdix), 
    #     #""" Read value no. <PIDX> from the temporary pattern memory.
    #     #"""
    # #)
    
    
    def set_mode(self, axis, mode):
        """ Set axis <AID> to mode <AMODE>.  Be sure to switch to the right mode 
        whenever you are measuring capacitance or attempting to move the positioner. 
        For sensitive, low noise measurements switch to GND
        """
        self.write("setm " + str(axis) + " "  + mode)

    def get_m(self, axis):
        """ Returns the axis mode: ext, stp, gnd, cap
        """
        self.write("getm " + str(axis))
        return self.read() 
          
    
    def stop(self, axis):
        """ Stop any motion on a given axis. 
        """
        self.write("stop " + str(axis))
        
    
    def stepu(self, axis, C):
        """ Move <C> steps or continuously upwards (outwards). An error occurs when the 
        axis is not in “stp” mode. 
        """
        self.write("stepu " + str(axis) + " "  +  str(C))
        
      
    def stepd(self, axis, C):
        """ Move number of steps or continuously downwards (inwards).
        """
        self.write("stepd " + str(axis)  + " "  +  str(C))    
    
    def get_f(self, axis):
        """ Set the frequency on axis <AID> to <FRQ>. 
        """
        self.write("getf " + str(axis))
        return self.read()   
   
    def set_f(self, axis, frq):
        """ Set the frequency on axis <AID> to <FRQ>. 
        """
        self.write("setf " + str(axis)  + " "  +  str(frq))

        
    def set_v(self, axis, vol):
        """ Set the frequency on axis <AID> to <vol>. 
        """
        self.write("setv " + str(axis)  + " "  +  str(vol))

    def get_v(self, axis):
        """ Returns the voltage
        """
        self.write("getv " + str(axis))
        return self.read() 
                
    
    def setpu(self, axis, pnum):
        """ Set pattern number <PNUM> for upward movement on axis <AID>.
        """
        self.write("setpu " + str(axis)  + " "  +  str(pnum))

        
    def setpd(self, axis, pnum):
        """ Set pattern number <PNUM> for downward movement on axis <AID>.
        """
        self.write("setpd " + str(axis)  + " "  +  str(pnum))
        
            
    def setp(self, axis, pidx, pval):
        """ Set value no. <PIDX> to value <PVAL> in the temporary pattern memory.
        """
        self.write("setp " + str(pidx)  + " "  +  str(pval))
        
                
    def resetp(self):
        """ Reset all patterns to factory defaults
        """
        self.write("resetp")

    def shut_down(self):
        del self.adapter