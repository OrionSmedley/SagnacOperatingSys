import numpy as np
from collections import OrderedDict
import numpy as np
import pandas as pd
import pymeasure
from time import sleep, time
from matplotlib import pyplot as plt
from matplotlib import style
from datetime import datetime
from pymeasure.instruments.keithley import Keithley2400, Keithley2000, Keithley2182A, Keithley6221
from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.srs import SR830, SR570
import matplotlib.cm as cm
from glob import glob
import os
import sys
import labdrivers.quantumdesign.qdinstrument as qd


ppms = qd.QdInstrument('PPMS','192.168.0.100')

nanovoltmeter = Keithley2182A("GPIB::9")
currentsource = Keithley2400("GPIB::24")

# voltmeter = Keithley2000("GPIB::14")
# currentsource2 = Keithley2400("GPIB::18")


li2 = SR830("GPIB::8")
li1 = SR830("GPIB::1")
currentsource = Keithley6221("GPIB::12")
