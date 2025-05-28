import telnetlib, time, socket
import time

class ANC300:
    def __init__(self):
        self.host = '192.168.1.5' #IP address for ANC300
        self.port= 7230 #standard telnet console port.  LUA console is at 7231
        self.timeout = 30
        self.password=b"123456"
        self.status=''
        self.identity=''
        self.connected=False

        # inacurate guestimates
        self.posX = 0
        self.posY = 0
        self.posZ = 0


    def connect(self):
        start_time=time.time()
        try:
            self.session = telnetlib.Telnet(self.host, self.port, self.timeout)
#             print(time.time()-start_time)
            self.identity = self.session.read_until(b"code: ",2).split(b"Authorization")[0]
#             print(time.time()-start_time)
            self.session.write(self.password+b"\r\n") #send default password
#             print(time.time()-start_time)
#             print(self.session.read_lazy())
            self.status = 'connected'
            self.connected = True
        except socket.timeout:
            self.status = "socket timeout"
            self.identity = 'none'
            self.connected = False    

        # test ANC300
        # self.status = 'connected'
        # self.identity = b'Mock ANC300'
        # self.connected = True
        # print("Mock: connected to ANC300")
        return self.identity

    def go(self,command):
        # print(f"Mock: go() called with {command}") #test
        # return b"Mock OK" #test
        self.session.write(command+b"\r\n")
        if(command[:3]==b"get"):
            received = self.session.read_until(b"OK", 2 )
        else:
            received = b"Done"
        return received.split(b"OK")[0]

    def stepu(self, axis, C):
        """ Move <C> steps or continuously upwards (outwards). An error occurs when the 
        axis is not in “stp” mode. 
        """

        axis_bytes = str(axis).encode('utf-8')
        C_bytes = str(C).encode('utf-8')

        self.go(b"stepu " + axis_bytes + b" "  +  C_bytes)
        
      
    def stepd(self, axis, C):
        """ Move number of steps or continuously downwards (inwards).
        """

        axis_bytes = str(axis).encode('utf-8')
        C_bytes = str(C).encode('utf-8')
        
        self.go(b"stepd " + axis_bytes + b" "  +  C_bytes) 

    def get_f(self, axis):
        """ Set the frequency on axis <AID> to <FRQ>. 
        """
        axis_bytes = str(axis).encode('utf-8')
        self.session.write(b"getf " + axis_bytes)
        received = self.session.read_until(b"OK", 2 )
        return axis_bytes
    
    def get_v(self, axis):
        """ Returns the voltage
        """
        axis_bytes = str(axis).encode('utf-8')
        self.session.write("getv " + str(axis))
        return self.session.read()    
        return axis_bytes
   

    def set_frequency(self, axis, frq):
        """ Set frequency for the specified axis. """
        axis_bytes = str(axis).encode('utf-8')
        frq_bytes = str(frq).encode('utf-8')
        self.go(b"setf " + axis_bytes + b" " + frq_bytes)
        print(frq)
        print(axis)
        print(frq_bytes)
        print(axis_bytes)

    def set_amplitude(self, axis, vol):
        """ Set amplitude (step voltage) for the specified axis. """
        axis_bytes = str(axis).encode('utf-8')
        vol_bytes = str(vol).encode('utf-8')
        self.go(b"setv " + axis_bytes + b" " + vol_bytes)
        print(vol)
        print(axis)
        print(vol_bytes)
        print(axis_bytes)

        
    
    def step(self, axis, steps):
        """ General method to move steps in positive or negative direction.
        axis: 4 for Z, 5 for Y, 6 for X.
        steps: Positive for upward movement, negative for downward movement.
        """
        if steps > 0:
            self.stepu(axis, steps)
        elif steps < 0:
            self.stepd(axis, abs(steps))
        else:
            print("No movement for zero steps.")

        # Update position based on axis
        if axis == 6:
            self.posX += steps
        elif axis == 5:
            self.posY += steps
        elif axis == 4:
            self.posZ += steps
    
    def stepx(self, steps):
        """ Move in X direction. """
        self.step(6, steps)

    def stepy(self, steps):
        """ Move in Y direction. """
        self.step(5, steps)

    def stepz(self, steps):
        """ Move in Z direction. """
        self.step(4, steps)

    def ground(self):
        """ Set X, Y, Z axes to Ground mode using real telnet commands. """
        # print("it got here")
        for axis in [6, 5, 4]:
            axis_bytes = str(axis).encode('utf-8')
            self.go(b"setm " + axis_bytes + b" gnd")
            # print("it got here " + str(axis))#test


    def unground(self):
        """ Set X, Y, Z axes to Step mode (i.e., unground) using real telnet commands. """
        # print("ungrounded got here") #test
        for axis in [6, 5, 4]:
            axis_bytes = str(axis).encode('utf-8')
            self.go(b"setm " + axis_bytes + b" stp")
            # print("ungrounded got here " + str(axis))  #test

    def capacitance(self):
        """ Set X, Y, Z axes to Capacitance mode using real telnet commands. """
        for axis in [6, 5, 4]:
            #print("1")
            axis_bytes = str(axis).encode('utf-8')
            self.go(b"setm " + axis_bytes + b" cap")
            #print("2")



    def get_capacitance(self,axis):
        time.sleep(1)
        # print("3")
        """ Get the measured capacitance value from the specified axis. Axis must be in CAP mode. """
        axis_bytes = str(axis).encode('utf-8')
        # print("4")

        self.session.write(b"getc " + axis_bytes + b"\r\n")   
        # print("5")
        
        
        # Step 2: Send getc command
        # IF ANYONE WANTS AN EXPLAINATION IT IS BECAUSE THE RESPONSE IS CHECKING THE ENTIRE READ UNTIL IT FINE THE "DO NOT CHANGE THIS" IF IT DOESN'T FIND IT OUTPUTS ALL OF IT WHICH WE WANT
        #DO NOT TRY TO CHANGE UNLESS U KNOW HOW TO GET A SPECIFIC READOUT
        response = self.session.read_until(b"DO NOT CHANGE THIS", .1).decode('utf-8')
        # print("6")
        # Step 3: Extract numeric capacitance value
        return(response)



## example of how to step on sagnac 3
# stepper.stepu(6, 2) #pos X
# stepper.stepd(6, 2) #neg X
# stepper.stepu(5, 2) #pos Y
# stepper.stepd(5, 2) #neg Y
# stepper.stepd(4,1) #neg Z
# stepper.stepu(4,1) #pos Z