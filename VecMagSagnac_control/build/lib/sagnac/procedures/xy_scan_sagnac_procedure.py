from time import sleep, time
import sys
import numpy as np
import pyvisa
import logging

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter



from scanning import ANC150
#from pymeasure.instruments.signalrecovery import DSP7265
from pymeasure.instruments.keithley import Keithley2400, Keithley2182A
from pymeasure.instruments.zurich import HF2LI
from ..instruments.LTC20 import LTC20
from pymeasure.instruments.keithley import Keithley6221
from pymeasure.adapters import DAQmxAdapter


class xy_scan_sagnac_procedure(Procedure):

	"""
	Procedure for performing scans in the xy-plane with attocube ANC150
	"""


	#DATA_COLUMNS = ["ThetaK", "x_pos"]

	queued_time = Parameter('Time Queued')
	calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'

	sample_name = Parameter("Sample Name", default='')

	fast_start = IntegerParameter("Offset fast: ", default = 0)
	slow_start = IntegerParameter("Offset slow: ", default = 0)

	forw_total = IntegerParameter("Total fast forward: ", default = 80)
	back_total = IntegerParameter("Total fast backward: ", default = 90)
	slow_total = IntegerParameter("Total slow: ", default = 100)
	slow_return_total = IntegerParameter("Total slow return steps: ", default = 100)

	forw_step = IntegerParameter("Step size fast forward: ", default = 1)
	back_step = IntegerParameter("Step size fast backward: ", default = 1)
	slow_step = IntegerParameter("Step size slow: ", default = 1)
	slow_return_step = IntegerParameter("Step size slow return", default = 1)

	fast_voltage = IntegerParameter("Fast voltage: ", default = 35)
	slow_voltage = IntegerParameter("Slow voltage: ", default = 35)

	fast_frequency = IntegerParameter("Fast frequency: ", default = 1000)
	slow_frequency = IntegerParameter("SLow frequency: ", default = 1000)

	fast_slow = Parameter("Fast / Slow Axes: ", default = "x / y")

	x_pos_start = IntegerParameter("Starting x coordinate", default = 0)
	y_pos_start = IntegerParameter("Starting y coordinate", default = 0)

	x_pos_end = IntegerParameter("Final x coordinate", default = 0)
	y_pos_end = IntegerParameter("Final y coordinate", default = 0)

	x_pos_step = IntegerParameter("Step in x", default = 0)
	y_pos_step = IntegerParameter("Step in y", default = 0)



	delay = FloatParameter("Step Delay: ", default = 0.1)

	x_axis = 1
	y_axis = 2

	settling = FloatParameter("Settling", units="s", default=0.5)
	wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
	avgs = IntegerParameter("Averages", default=1)
	first = True
	last = True
	#DATA_COLUMNS = ["x_pos", "y_pos", "ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2", "elapsed_time"]


	#DATA_COLUMNS = ["x_pos"]#, "y_pos", "ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2", "step", "elapsed_time"]

	DATA_COLUMNS = ["x_pos", "y_pos", "ThetaK","X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2", "elapsed_time"]
	
	def startup(self):
		log.info("Connecting and configuring the instruments")

		if self.fast_slow == "x / y":
			fast = self.x_axis
			slow = self.y_axis
		else:
			fast = self.y_axis
			slow = self.x_axis


		#self.lockin = DSP7265("GPIB::12")

		self.stepper = ANC150("COM3")

		self.stepper.set_f(fast, self.fast_frequency)
		self.stepper.set_v(fast, self.fast_voltage)
		self.stepper.set_mode(fast, 'stp')

		self.stepper.set_f(slow, self.slow_frequency)
		self.stepper.set_v(slow, self.slow_voltage)
		self.stepper.set_mode(slow, 'stp')


		sleep(self.wait) 

		log.info("Connecting to the Zurich Lock-in")
		self.lockin = HF2LI(8005,1,1004)
		# log.info(f'Outputing {self.applied_voltage} on output 2 osc 0')
		# self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
		#subscribe to outputs
		self.lockin.sub(0)
		self.lockin.sub(1)
		# self.lockin.sub(2)
		self.lockin.sub(3)
		self.lockin.sub(4)
		self.lockin.sub(5)



	def execute(self):
		print(self.delay)

		J2J1 = 0.543
		J1J0 = 1.837
		deg2rad = np.pi/180.
		start_time = time()

		if self.fast_slow == "x / y":
			fast = self.x_axis
			slow = self.y_axis
		else:
			fast = self.y_axis
			slow = self.x_axis


		if self.fast_start > 0:
			for i in range(0, self.fast_start, self.forw_step):
				self.stepper.stepu(fast, self.forw_step)
				sleep(self.delay)
				 
		else:
			for i in range(0, -1 * self.fast_start, self.forw_step):
				self.stepper.stepd(fast, self.forw_step)
				sleep(self.delay)

		if self.slow_start > 0:
			for i in range(0, self.slow_start, self.slow_step):
				self.stepper.stepu(slow, self.slow_step)
				sleep(self.delay)

		else:
			for i in range(0, -1 * self.slow_start, self.slow_step):
				self.stepper.stepd(slow, self.slow_step)
				sleep(self.delay)




		num_progress = (self.forw_total/ self.forw_step ) * (self.slow_total / self.slow_step)
		log.info(str(num_progress))

		#forward = True

		for slow_progress in range(0, self.slow_total, self.slow_step):

			#log.info("x_progress")# + str(x_progress))
			for fast_forw_progress in range(0, self.forw_total, self.forw_step):
				
				log.info(str(fast_forw_progress))
				fast_pos =  fast_forw_progress / self.forw_step
				slow_pos = slow_progress / self.slow_step


				dat_list = []
				for i in range(self.avgs):
					self.lockin.sync() # clears buffer since field has changed
					sleep(self.settling)
					self.lockin.sync() # clears buffer since field has changed
					log.info("recording average #%d"%i)
					dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
				dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

				if self.fast_slow == "x / y":
					log.info("(x = " + str(fast_pos) + ", " + "(y = " + str(slow_pos))
					self.emit('results', {
						"x_pos": fast_pos,
						"y_pos": slow_pos,
						"ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
						"X1": dat[3]['x'],
						"Y1": dat[3]['y'],
						"X2": dat[5]['x'],
						"Y2": dat[5]['y'],
						"DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y'],
						"DeltaX1": dat[4]['x'],
						"DeltaY1": dat[4]['y'],
						"TX1": dat[0]['x'],
						"TY1": dat[0]['y'],
						"TX2": dat[1]['x'],
						"TY2": dat[1]['y'],
						"elapsed_time": time() - start_time
						})

				else:
					log.info("(x = " + str(slow_pos) + ", " + "(y = "+ str(fast_pos))
					self.emit('results', {
						"x_pos": slow_pos,
						"y_pos": fast_pos,
						"ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
						"X1": dat[3]['x'],
						"Y1": dat[3]['y'],
						"X2": dat[5]['x'],
						"Y2": dat[5]['y'],
						"DeltaThetaK": J2J1*dat[4]['x']/dat[5]['y'],
						"DeltaX1": dat[4]['x'],
						"DeltaY1": dat[4]['y'],
						"TX1": dat[0]['x'],
						"TY1": dat[0]['y'],
						"TX2": dat[1]['x'],
						"TY2": dat[1]['y'],
						"elapsed_time": time() - start_time
						})

				self.stepper.stepu(fast, self.forw_step)
				#log.info("Fast axis forward" + str( 100 * fast_forw_progress / self.forw_total) + "%")

				complete = (slow_progress / self.slow_step * self.forw_total / self.forw_step) + (fast_forw_progress / self.forw_step)

				self.emit("progress", int(100*complete / num_progress))
				sleep(self.delay)
				#log.info("Recording results")
				if self.should_stop():
					log.warning("Caught stop flag in procedure.")
					break


			for fast_back_progress in range(0, self.back_total, self.back_step):
				self.stepper.stepd(fast, self.back_step)
				sleep(self.delay)
				#log.info("Fast axis backward: " + str( 100 * fast_back_progress / self.back_total) + "%")
				if self.should_stop():
					log.warning("Caught stop flag in procedure.")
					break



			self.stepper.stepu(slow, self.slow_step)
			#log.info("Slow step: " + str(100*slow_progress / self.slow_total))
			if self.should_stop():
				log.warning("Caught stop flag in procedure.")
				break


		for slow_return in range(0, self.slow_return_total, self.slow_return_step):
			self.stepper.stepd(slow, self.slow_return_step)
			sleep(self.delay)
			#log.info("Slow axis return: " + str(slow_return / self.slow_return_total))
			if self.should_stop():
				log.warning("Caught stop flag in procedure.")
				break






	def shutdown(self):
		self.stepper.shut_down()
