import logging

import socket
from .adapter import Adapter

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class AmetekIPAdapter(Adapter):
    """
    IP Adapter for Ametek DSP 7270. Needed because it
    has strange ending character combination that PyVISA can't handle
    """

    def __init__(self, socket_string, **kwargs):

        adapter_type, ipaddr, portno = socket_string.split("::")

        self.address = (str(ipaddr),int(portno))
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.sock.connect(self.address)
        self.sock.settimeout(0.01)
        self.write_term = '\x00'
        self.good_read_term = '\n\x00\x35\x00' # what we expect to recieve if transmission worked


    def __del__(self):
        """
        ensures the socket is closed
        """
        self.sock.close()

    def write(self,command):
        try: # Receive buffer will get stuck if we are issuing write-only commands
            self.sock.recv(2048)
        except:
            pass
        mesg_term = command + self.write_term
        self.sock.send(mesg_term.encode())

    def read(self):
        incoming = self.sock.recv(2048).decode()
        incoming = incoming[:-4] # taking off the status bits, should always work
        return incoming

    def __repr__(self):
        return "<AmetekIPAdapter(IP address='%s',port no='%d')>" % self.address
