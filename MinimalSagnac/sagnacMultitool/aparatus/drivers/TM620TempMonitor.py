import pyvisa
import time
import re

"""Initialize connection to TM-622 via Ethernet."""
class TM620:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource("TCPIP0::169.254.62.184::4266::SOCKET")
        self.instrument.timeout = 2000
        self.instrument.read_termination = '\r\n'
        self.instrument.write_termination = '\r\n'

    def query(self,command):
        """Send a query command and return the response."""
        return self.instrument.query(command)

    def write(self,command):
        """Send a write command."""
        self.instrument.write(command)
        
    def set_channel(self,subch):
        """Send a command to change to subchannel to {channel}"""
        # print(f"Changing to subchannel {subch}")
        check = False
        self.instrument.write(f"SUBCH {subch}")
        time.sleep(0.07)
        if subch == 'B':
            while check == False:
                response = self.instrument.query(f"SUBCH?")
                check = self.parse_channel(response)
                # print(f"Subchannel is now: {self.channel}")
            return check
        elif subch == 'A':
            while check == False:
                response = self.instrument.query(f"SUBCH?")
                check = self.parse_channel(response)
                # print(f"Subchannel is now: {self.channel}")
            return check

    def get_channel(self):
        check = False
        while check == False:
            response = self.instrument.query(f"SUBCH?")
            check = self.parse_channel(response)
        return check

    channel = property(get_channel, set_channel)

    def parse_temp(self,response,doublecheck):
        """Extract temperature value from the response."""
        # print(f"response is: {response}")  USE FOR DEBUGGING 
        match = re.findall(r"([A-Za-z]):\s*([\d.]+)K", response)
        if match == []:
            return False 
        else:
            if match[0][0] == 'B' or match[0][0] == 'A':
                if match[0][0] == doublecheck:
                    return float(match[0][1])
                else:
                    return False

    def parse_channel(self,response):
        """Extract temperature value from the response."""
        # print(f"response is: {response}")  #USE FOR DEBUGGING 
        match = re.findall(r"([A-Za-z]):\s*([\d.]+)K", response)
        # print(f"match is: {match}")
        if match == []:
            return response 
        else:
            if match[0][0] == 'B' or match[0][0] == 'A':
                if match[0][0] == 'B':
                    return 'b'
                else:
                    return 'a'
        
    def get_Tmag(self):
        """Read temperature from a specific channel."""
        subch = self.channel
        check = False
        # print(f"Subchannel is {self.channel}")
        if subch == "b":
            while check == False:
                response = self.instrument.query(f"MEAS?")
                check = self.parse_temp(response,'B')
            return check
        else:
            while check == False:
                # print("Selecting Magnet Subchannel")
                subch = self.set_channel("B")
                self._channel = self.get_channel()
                response = self.instrument.query(f"MEAS?")
                check = self.parse_temp(response,'B')    
            return check

    def get_Tshield(self):
        """Read temperature from a specific channel."""
        subch = self.channel
        check = False
        # print(f"Subchannel is {self.channel}")
        if subch == "a":
            while check == False:
                response = self.instrument.query(f"MEAS?")
                check = self.parse_temp(response,'A')
            return check
        else:
            while check == False:
                # print("Selecting Magnet Subchannel")
                subch = self.set_channel("A")
                self._channel = self.get_channel()
                response = self.instrument.query(f"MEAS?")
                check = self.parse_temp(response,'A')    
            return check
        
    def set_Tmag():
        return None
    
    def set_Tshield():
        return None

    Tmag = property(get_Tmag, set_Tmag)
    Tshield = property(get_Tshield, set_Tshield)

    def close(self):
        """Close the connection."""
        self.instrument.close()
        
# import pyvisa
# import time
# import re

# """Initialize connection to TM-622 via Ethernet."""
# class TM620:
#     def __init__(self):
#         self.rm = pyvisa.ResourceManager()
#         self.instrument = self.rm.open_resource("TCPIP0::169.254.62.184::4266::SOCKET")
#         self.instrument.timeout = 2000
#         self.instrument.read_termination = '\r\n'
#         self.instrument.write_termination = '\r\n'

#     def query(self,command):
#         """Send a query command and return the response."""
#         return self.instrument.query(command)

#     def write(self,command):
#         """Send a write command."""
#         self.instrument.write(command)
        
#     def set_channel(self,subch):
#         """Send a command to change to subchannel to {channel}"""
#         # print(f"Changing to subchannel {subch}")
#         self._channel = self.instrument.query(f"SUBCH?")
#         # print(f"Subchannel is now: {self._channel}")
#         self.instrument.write(f"SUBCH {subch}")
#         time.sleep(0.02)

#     def get_channel(self):
#         check = False
#         while check == False:
#             response = self.instrument.query(f"SUBCH?")
#             check = self.parse_channel(response)
#         return check

#     channel = property(get_channel, set_channel)

#     def parse_temp(self,response,doublecheck):
#         """Extract temperature value from the response."""
#         # print(f"response is: {response}")  USE FOR DEBUGGING 
#         match = re.findall(r"([A-Za-z]):\s*([\d.]+)K", response)
#         if match == []:
#             return False 
#         else:
#             if match[0][0] == 'B' or match[0][0] == 'A':
#                 if match[0][0] == doublecheck:
#                     return float(match[0][1])
#                 else:
#                     return False

#     def parse_channel(self,response):
#         """Extract temperature value from the response."""
#         # print(f"response is: {response}")  USE FOR DEBUGGING 
#         match = re.findall(r"([A-Za-z]):\s*([\d.]+)K", response)
#         if match == []:
#             return response 
#         else:
#             if match[0][0] == 'B' or match[0][0] == 'A':
#                 if match[0][0] == 'B':
#                     return 'b'
#                 else:
#                     return 'a'
        
#     def Tmag(self):
#         """Read temperature from a specific channel."""
#         subch = self.channel
#         check = False
#         # print(f"Subchannel is {self.channel}")
#         if subch == "b" or subch == "B":
#             while check == False:
#                 response = self.instrument.query(f"MEAS?")
#                 check = self.parse_temp(response,'B')
#             return check
#         else:
#             while check == False:
#                 # print("Selecting Magnet Subchannel")
#                 subch = self.set_channel("B")
#                 time.sleep(0.02)
#                 self._channel = self.get_channel()
#                 time.sleep(0.02)
#                 response = self.instrument.query(f"MEAS?")
#                 check = self.parse_temp(response,'B')    
#             return check

#     def Tshield(self):
#         """Read temperature from a specific channel."""
#         subch = self.channel
#         check = False
#         # print(f"Subchannel is {self.channel}")
#         if subch == "a" or subch == "A":
#             while check == False:
#                 response = self.instrument.query(f"MEAS?")
#                 check = self.parse_temp(response,'A')
#             return check
#         else:
#             while check == False:
#                 # print("Selecting Magnet Subchannel")
#                 subch = self.set_channel("A")
#                 time.sleep(0.02)
#                 self._channel = self.get_channel()
#                 time.sleep(0.02)
#                 response = self.instrument.query(f"MEAS?")
#                 check = self.parse_temp(response,'A')    
#             return check

#     def close(self):
#         """Close the connection."""
#         self.instrument.close()

