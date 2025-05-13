# from time import sleep, time
# import logging
# log = logging.getLogger(__name__)
# log.addHandler(logging.NullHandler())

# import numpy as np
# from pymeasure.instruments.validators import truncated_range
# from pymeasure.instruments import Instrument
# import pyvisa

# from aparatus.drivers import TM620TempMonitor
# TM620 = TM620TempMonitor.TM620()

# class MPSHZ:
    
#     def __init__(self, IPAddress):
#         self.resourcestr = f"TCPIP0::{IPAddress}::4444::SOCKET"
#         self.rm = pyvisa.ResourceManager()
#         self.instrument = self.rm.open_resource(f"TCPIP0::{IPAddress}::4444::SOCKET")
#         self.instrument.read_termination = '\r\n'
#         self.instrument.write_termination = '\r\n'
    
#     def connect(self):
#         self.rm = pyvisa.ResourceManager()
#         self.instrument = self.rm.open_resource(self.resourcestr)
#         self.instrument.read_termination = '\r\n'
#         self.instrument.write_termination = '\r\n'
        
#     def disconnect(self):
#         if self.instrument:
#             self.instrument.close()
    
#     def query(self, command):
#         return self.instrument.query(command)

#     def write(self, command):
#         self.instrument.write(command)

#     def set_channel(self, channel):
#         self.write(f'CHAN {int(channel)}')
#         res = self.query('CHAN?')
#         return res

#     def get_field(self):
#         value = np.nan
#         while np.isnan(value):
#             try:
#                 res = self.query('IMAG?')
#                 value = float(res.replace('kG', ''))
#                 return value
#             except:
#                 value =  np.nan
#                 sleep(1)
                
#     def pause_field(self):
#         response = self.query('SWEEP?')
#         # print(f"Response is {response}")
#         while response != 'Pause':
#             self.write('SWEEP PAUSE')
#             sleep(0.05)
#             response = self.query('SWEEP?')
#             print(f"Mag ramp now set to {response}")    
        
#     def temp_check(self, Tthresh):
#         Tmag = TM620.Tmag
#         if Tmag > float(Tthresh):
#             print(f"Woah magnet temp is higher than {Tthresh}. Pausing ramp to cool down.")
#             while Tmag > (Tthresh):
#                 sleep(2)
#                 print(f"Waiting for magnet to cool from {Tmag} to {(Tthresh)}")
#                 return False
#         else:
#             return True        
            
#     def set_field(self, field):
#         current_field = self.get_field()
#         sleep(0.1)
#         if field - current_field > 0.001:
#             self.write(f'ULIM {field}')
#             sleep(0.1)
#             self.write('SWEEP UP')
#         elif field - current_field < -0.001:
#             self.write(f'LLIM {field}')
#             sleep(0.1)
#             self.write('SWEEP DOWN')
#         else:
#             pass

#     def check_field(self, set_field, tol = 0.001):
#         current_field = self.get_field()
#         if abs(set_field - current_field) > tol:
#             return False
#         else:
#             return True    

#     def is_ramping(self):
#         check = self.query('SWEEP?')
#         # print(f"Ramping check is {check}")
#         return check

#     def zero_field(self):
#         self.write('SWEEP ZERO')


# class Magnet_highZ:
    
#     ATOL = 1e-3
#     def __init__(self, limit = 40):
#         self.device_z = MPSHZ('169.254.62.187')
#         self.device_2 = MPSHZ('169.254.62.188')
#         self._field_difference_cutoff = 1e-3 #1e-5 # 0.1 G
#         self._field_mag_lim = limit # bootleg version is kG, previous auttodry gui was T
#         # self._B_sign = 1 #Not sure what this is for. Delete? 2025/01/24 - Orion and Ethan

#         # limit such that below this field change the magnet does not actually change field,
#         # to limit commands sent to the magnet

#         self._B_sign = 1 
        
#         self._Toverheat = 4.4
#         self._Tcooling = (self._Toverheat - 0.25)
#         self._Tflag = (self._Toverheat - 0.12)
#         self._flag = 1


#         # self.Bx_set, self.By_set, self.Bz_set = self.get_field_cartesian()
#         # self.B_set, self.phi_set, self.theta_set = self.get_field_polar()

#     def connect_highZ(self):
#         self.device_z.write("REMOTE")
#         self.device_2.write("REMOTE")
#         Bx, By, Bz = self.get_field_cartesian()
#         print("Connecting. The field is", np.sqrt(Bx*Bx + By*By + Bz*Bz))
        
#         self.Bx, self.By, self.Bz = self.get_field_cartesian()
        
#         if np.abs(Bz) > 9.9:
#             if np.abs(Bx) > 0 or np.abs(By) > 0:
#                 self.device_z.disconnect()
#                 self.device_2.disconnect()
#                 print("Bmag vector is larger than 0.9 T! Don't touch anything else! Call Ethan or Kelly")
#                 raise ValueError("Bmag vector is larger than 0.9 T! Don't touch anything else! Call Ethan or Kelly")
#             else:
#                 print("Not zeroing Bx and By, because if useful, you were already screwed.")
#         else:
#             print("Zeroing X magnet")
#             self.device_2.set_channel(1)
#             self.device_2.zero_field()

#             print("Zeroing Y magnet")
#             self.device_2.set_channel(2)
#             self.device_2.zero_field()

#         print("disconnecting from x and y for safety")
#         self.device_2.disconnect()
        
#     def get_Bz(self):
#         """Returns the magnitude of the field."""
#         return np.sqrt(self.Bz**2)

#     def set_field_highZ(self, Bz):
#         log.info('Setting Bz to : %g'%(Bz))
#         if np.abs(self.Bz) > self._field_mag_lim: #np.sqrt returns positive square root
#             log.error("A large field of %g was requested"%Bz)
#             raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)
        
#         self.device_z.set_field(Bz)
        
#     def setSafe_wait(self, junk = 0):
#         # print("1")
#         tic = time()
#         # print("2")
#         Bz_init = self.get_field_highZ()
#         # print("3")
#         # print(f"Bz initial: {Bx_init, By_init, Bz_init}")
#         mag_safe = self.check_temps()
#         # print("4")
#         # print(f"Mag safe 1 is {mag_safe}")
#         if mag_safe != None:
#             if not np.abs(self.Bz) > np.abs(Bz_init): 
#                 # print("entering if")
#                 while not self.check_field_highZ(self.Bz, 10*self.ATOL):
#                     print("waiting for z to ramp down")
#                     mag_safe = self.check_temps()
#                     # print(f"Mag safe 3 is {mag_safe}")
#                     sleep(0.1)
#                     if mag_safe == True:
#                         self.set_field_highZ(self.Bz)
#                         sleep(0.1)
#                         print(f"waiting for z to ramp down {time()-tic}")
#             while not self.check_field_highZ(self.Bz, self.ATOL):
#                 mag_safe = self.check_temps()
#                 # print(f"Mag safe 4 is {mag_safe}")
#                 sleep(0.1)
#                 if mag_safe == True:
#                     self.set_field_highZ(self.Bz)
#                     sleep(0.1)
#                     print(f"waiting for mag for {time()-tic}")

#     def get_field_highZ(self):
#         Bz = self.device_z.get_field()
#         return Bz
    
#     def get_field_cartesian(self):
#         """
#         Returns the cartesian parameterization of the field in the order X, Y, Z.
#         """
#         # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
#         self.device_2.query("*IDN?")
#         self.device_2.set_channel(1) # x
#         Bx = self.device_2.get_field()
#         # print(Bx)
#         self.device_2.set_channel(2) # y
#         By = self.device_2.get_field()
#         # print(By)
#         Bz = self.device_z.get_field()
#         # print(Bz)
#         return Bx, By, Bz

#     def check_field_highZ(self, Bset, ATOL):
#             """Checks the current field value to make sure it is within absolute tolerance of setpoint """
#             Bz = self.get_field_highZ()

#             print(f"Currently Bz = {Bz}") #redundant, if you use the monkypatch for pymeasure

#             if np.isclose(Bset, Bz, atol=ATOL):
#                 log.info("Field is close to the setpoint")
#                 return True
#             else:
#                 log.info(f"Currently Bz = {Bz}")
#                 return False
            
#     def check_temps(self):
#         """Checks the Magnet Thermometer Temperature to know if the ramp rate needs to be paused"""
#         bigcheck = self.device_z.temp_check(self._Toverheat)
#         shield = TM620.Tshield
        
#         if bigcheck == True and shield <= 55:
#             bigcheck == True
#         else: 
#             bigcheck == False
        
#         # print(f"bigcheck 1 is {bigcheck}")
            
#         if bigcheck != False:
#             secondcheck = self.device_z.temp_check((self._Tflag))        
#             if secondcheck == False or self._flag == 2:
#                 self._flag = 2
#                 print(f"Overheat flag is up")
#                 while self._flag != 1:
#                     # print(f"Threshold is {self._Tcooling}")
#                     print(f"Flag is up")
#                     zcheck = self.device_z.temp_check(self._Tcooling)
                    
#                     # print(f"Zcheck 1 is {zcheck}")
                    
#                     if zcheck == True:
#                         self._flag = 1
#                         print(f"FLAG IS NOW RESET")
#                         return True
                    
#                     else:
#                         check1 = self.device_z.is_ramping()
#                         # print(f"Check1 is {check1}")
#                         if check1 != "Pause" or check1 != "Standby":
#                             self.device_z.pause_field()

#                         zcheck = self.device_z.temp_check(self._Tcooling)
                        
#                         return False
#             elif secondcheck == True:
#                 if self._flag == 1:
#                     return True 
                
#         else: 
#             if shield > 55:
#                 print("Shield is too hot, stop this, call Ethan ASAP before ramping magnet or Kelly")
#             else:
#                 print("Magnet is too hot, stop this, call Ethan ASAP before ramping magnet or Kelly")
                
#             return None
            
#     def shutdown(self):
#         """
#         Shuts down each of the magnets individually
#         """
#         log.info("Shutting down only the Z magnet")
#         self.device_z.zero_field()
        
#         try:
#             self.device_z.disconnect()
#         except:
#             print("No device z to disconect")