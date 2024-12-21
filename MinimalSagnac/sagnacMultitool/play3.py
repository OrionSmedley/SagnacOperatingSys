# from aparatus.sagnac3 import keith1, keith2, myHF2LI, mag     
# mag.safeWaitCart(0,0,0)
# mag.set_field_cartesian(0,0,0)
# print(myHF2LI.dem(3))




# from aparatus.drivers.magnet_usbCom import vectorMagnetFullUSB
# mag = vectorMagnetFullUSB()
# mag.set_field_cartesian(1,0,0)

#################################################################################

import sys
module_dir = r"D:\Github\SagnacOperatingSys\VecMagSagnac_control"
sys.path.append(module_dir)
from sagnac.custom_instruments import vectorMagnetFullUSB
mag = vectorMagnetFullUSB()
mag.connect()


import atto_device.CRYO2100 as cr
atto = cr("192.168.1.1")
atto.connect()





import time

Tthresh = 4.2
ATOL = 1e-3
def setSafe_wait_cart(bx,by,bz):
    temp = atto.condenser.getTemperature()
    if temp >Tthresh:
        # atto.disconnect() 
        print( f"yikes, resevoir at {temp}C > max {Tthresh}")
        mag.shutdown()
        raise RuntimeError(f"shut down bc resevoir at {temp}C > max {Tthresh}")

    
    mag.set_field_cartesian(bx,by,bz)

    tic = time.time()
    while not mag.check_field_cartesian(bx, by, bz, ATOL):
        time.sleep(0.1)
        print(f"waiting for mag for {time.time()-tic}")

# setSafe_wait_cart(0.01,0.02,0.03)

mag.setSafeWaitBx = lambda b: setSafe_wait_cart(b,0,0)
mag.setSafeWaitBy = lambda b: setSafe_wait_cart(0,b,0)
mag.setSafeWaitBz = lambda b: setSafe_wait_cart(0,0,b)

mag.setSafeWaitBx(0.04)
input("like this?")
mag.setSafeWaitBy(0.04)


# mag.set_field_cartesian(0.01,0,0)




# #################################

# import sys
# import time
# from atto_device.CRYO2100 import CRYO2100

# # Add custom instruments module to path
# module_dir = r"D:\Github\SagnacOperatingSys\VecMagSagnac_control"
# sys.path.append(module_dir)
# from sagnac.custom_instruments import vectorMagnetFullUSB

# # Define safety threshold
# MAGTEMP_THRESHOLD = 4.2  # Example threshold in Kelvin
# FIELD_TOLERANCE = 3e-4  # Tolerance for field stability

# # Initialize and connect to devices
# mag = vectorMagnetFullUSB()
# mag.connect()

# atto = CRYO2100("192.168.1.1")
# atto.connect()

# def check_temperature():
#     """Check if the magnet temperature is below the threshold."""
#     magtemp = float(atto.condenser.getTemperature())
#     if magtemp >= MAGTEMP_THRESHOLD:
#         raise ValueError(f"Temperature {magtemp} exceeds safety threshold {MAGTEMP_THRESHOLD}K.")
#     print(f"Temperature check passed: {magtemp}K")
#     return magtemp

# def wait_for_field_setpoint(Bx, By, Bz, tolerance=FIELD_TOLERANCE, max_attempts=100, interval=0.5):
#     """Wait for the magnet field to reach the setpoint."""
#     attempts = 0
#     while attempts < max_attempts:
#         if mag.check_field_cartesian(Bx, By, Bz, tolerance):
#             print(f"Field reached setpoint: Bx={Bx}, By={By}, Bz={Bz}")
#             return
#         print(f"Waiting for field to stabilize. Attempt {attempts + 1}/{max_attempts}...")
#         time.sleep(interval)
#         attempts += 1
#     raise TimeoutError(f"Magnet field did not stabilize within {max_attempts * interval} seconds.")

# def set_field_safely(Bx, By, Bz):
#     """Set the magnetic field safely."""
#     check_temperature()
#     mag.set_field_cartesian(Bx, By, Bz)
#     wait_for_field_setpoint(Bx, By, Bz)

# # Example usage
# try:
#     set_field_safely(0.01, 0.02, 0.03)  # Set the desired field values in Tesla
# except Exception as e:
#     print(f"Error: {e}")
# finally:
#     atto.disconnect()
#     mag.shutdown()

