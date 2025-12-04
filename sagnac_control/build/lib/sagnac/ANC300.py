import telnetlib, time, socket

class ANC300:
    def __init__(self):
        self.host = '192.168.1.5' #IP address for ANC300
        self.port= 7230 #standard telnet console port.  LUA console is at 7231
        self.timeout = 30
        self.password=b"123456"
        self.status=''
        self.identity=''
        self.connected=False

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

        return self.identity

    def go(self,command):
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
        return received
   
    # def set_f(self, axis, frq):
    #     """ Set the frequency on axis <AID> to <FRQ>. 
    #     """
    #     self.session.write("setf " + str(axis)  + " "  +  str(frq) + +b"\r\n")

        
    # def set_v(self, axis, vol):
    #     """ Set the frequency on axis <AID> to <vol>. 
    #     """
    #     self.session.write("setv " + str(axis)  + " "  +  str(vol))

    def get_v(self, axis):
        """ Returns the voltage
        """
        self.session.write("getv " + str(axis))
        return self.session.read()  