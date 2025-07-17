"""
clerk.py - Utility functions for experimenter.py

Sometimes you're too lazy to write out lists of parameters for your experiments.
Let the clerk do it for you!

"""

import numpy as np
import pandas as pd
import time

# repeat = None  # doesn't do anything, just a convenient dummy variable for use in experimenter.py
# subSample = None  # doesn't do anything, just a convenient dummy variable for use in experimenter.py
# purpose = None # doesn't do anything, just a convenient dummy variable for use in experimenter.py
queueT = pd.Timestamp.now() # doesn't do anything, just a convenient dummy variable for use in experimenter.py

class Counter:
    def __init__(self):
        # start at –1 so the first call gives you “0”
        self.cnt = -1

    def __call__(self, numSweeps):
        """
        Counts how many times it has run, modulo numSweeps.
        Usage in your experiment csv file:
          parameters = {
            'sweep': [4],  # number of sweep items to track
            'something': hysteresis(np.linspace(0,1,10), bipolar=True),
          }
        Then in your code you’d do:
          sweep_counter(numSweeps)
        """
        self.cnt = (self.cnt + 1) % numSweeps
        return self.cnt


# def counter(numSweeps):
#     """
#     Counts how many time it has run, modulo numSweeps.

#     Usage in your experiment csv file:
#     parameters = { 
#       'sweep': [4], #number of sweep items to track
#       'something": hysteresis(np.linspace(0, 1, 10), bipolar=True)
#       }

#     """
#     counter.cnt = (counter.cnt +1) % numSweeps
# counter.cnt = -1


def hysteresis(arr, bipolar=False):
    """
    Generates hysteresis sweep lists.
    
    Parameters:
        arr (numpy array or iterable): The base array representing the forward sweep.
        bipolar (bool): If True, returns four lists (bipolar hysteresis). 
                        If False, returns two lists (unipolar hysteresis).
    
    Returns:
        list: A list of NumPy arrays representing the hysteresis sweep.
              - If bipolar=True: [arr, reversed arr, -arr, -reversed arr]
              - If bipolar=False: [arr, reversed arr]
    
    Example:
        >>> x = np.arange(0, 0.2, 0.01)
        >>> hysteresis_sweep(x, bipolar=True)
        [array([0.  , 0.01, 0.02, ..., 0.19]),
         array([0.19, 0.18, 0.17, ..., 0.  ]),
         array([-0.  , -0.01, -0.02, ..., -0.19]),
         array([-0.19, -0.18, -0.17, ..., -0.  ])]
    """
    arr = np.asarray(arr)
    reversed_arr = arr[::-1]
    
    if bipolar: return [arr, reversed_arr, -arr, -reversed_arr]
    return [arr, reversed_arr]

def onesweepscanners(ysteps,xsteps,yrange,xrange):
    xarr = np.array(np.linspace(xrange[0],xrange[1],xsteps))
    yarr = np.array(np.linspace(yrange[0],yrange[1],ysteps))
    pts = []
    for i, y in enumerate(yarr):
        # snake pattern: reverse every other row
        xs = xarr[::-1] if (i % 2) else xarr
        for x in xs:
            pts.append((x, y))
    return pts, len(pts)

def fieldsweepscanners(fields,ysteps,xsteps,yrange,xrange):
    fields = np.array(fields)
    xarr = np.array(np.linspace(xrange[0],xrange[1],xsteps))
    yarr = np.array(np.linspace(yrange[0],yrange[1],ysteps))
    trio = []
    for j, field in enumerate(fields):
        pts = []
        for i, y in enumerate(yarr):
            # snake pattern: reverse every other row
            xs = xarr[::-1] if (i % 2) else xarr
            for x in xs:
                pts.append((x, y))
        if (j % 2): pts = pts[::-1]
        trio.extend((field, x, y) for x, y in pts)
    return trio, len(trio)

def field_to_db(field_quantity):
    return 20 * np.log10(field_quantity)

def db_to_field(db):
    return 10 ** (db / 20)

def waitUntil(condition):
    """
    Wait until the condition is true
    condition must be a function!
    example usage: 
        waitUntil(lambda: not magnet.in_motion)
    in a csv:
        parameters = {
        waitUntil: ["lambda: not magnet.in_motion"]
        }
    """
    while not condition():
        time.sleep(0.5)
        # print( "condition is ", condition())

    
# ## The following functions have been removed from experimenter.py and placed here for convenience ##
# ## heleper fuctions usable from csv file ##
# repeat =0 #doesn't do anything, just a convienient dummy variable

# ## heleper fuctions usable from csv file ##

def simplehysteresis(npArray):
    return np.concatenate([npArray, npArray[::-1]])