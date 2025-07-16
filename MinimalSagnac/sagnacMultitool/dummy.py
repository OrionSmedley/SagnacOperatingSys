import numpy as np
from time import sleep

class Instrument:
    def __init__(self):
        self.phase = 0
        self.frequency = 0
        self.temperature = 0
        self.junk = 100

    def get_voltage(self):
        # Simulate voltage based on current settings
        sleep(1)
        return [self.frequency * np.cos(self.phase) + self.temperature / 10]

    @property
    def current(self):
        # Simulate current based on current settings
        return self.frequency * np.sin(self.phase) + self.temperature / 20
    
    def set_junk(self, value):
        self.junk = value
        

# Create a global instance of the instrument
instrument = Instrument()

# # Export only the instance
# __all__ = ["instrument"]

#   %%
from clerk import Counter
# %%
c1 = Counter()
# %%
c1(4)
# %%
import numpy as np

array = np.arange(3)
temparray = []
for i in range(int(len(array))):
    print(array[int(i % (len(array)))])
    temparray.append(float(array[int(i % (len(array)))]))
    
print(temparray)
# %%
def onesweepscanners(ysteps,xsteps,yrange,xrange):
    xarr = np.array(np.linspace(xrange[0],xrange[1],xsteps))
    yarr = np.array(np.linspace(yrange[0],yrange[1],ysteps))
    tempx,tempy = [],[]
    for i in range(int(ysteps)):
        if i % 2 == 1:
            tempx.append(xarr[::-1])
        else:
            tempx.append(xarr)

    for i in range(int(ysteps)):
        tempy.append([yarr[i]]*len(xarr))
    return list(zip(tempx,tempy))

paired = onesweepscanners(2,5,[0,1],[0,1])

print(paired)
# %%
