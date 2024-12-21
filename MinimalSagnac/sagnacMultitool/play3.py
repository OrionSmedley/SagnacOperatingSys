from aparatus.sagnac3 import keith1, keith2, myHF2LI, mag     
dem = myHF2LI.dem
parameters = {}

# this should have gone into the driver ... opps!
def setXmag(b): mag.safeWaitCart(b,0,0)
def setYmag(b): mag.safeWaitCart(0,b,0)
def setZmag(b): mag.safeWaitCart(0,0,b)



laserPow =  165 #mA
lasertemp = 21.5 #C
startI = -1e-3
stopI = 1e-3

setZmag(-0.01)