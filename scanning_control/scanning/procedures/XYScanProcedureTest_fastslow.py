from time import sleep, time
import sys
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np

from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter

# from pymeasure.instruments.attocube import ANC150
from scanning import ANC150
from pymeasure.instruments.signalrecovery import DSP7265
import pyvisa


class XYScanProcedureTest_fastslow(Procedure):

	"""
	Procedure for performing scans in the xy-plane with attocube ANC150
	"""
	queued_time = Parameter('Time Queued')

	sample_name = Parameter("Sample Name", default='')
	DATA_COLUMNS = ["X", "Y", "x_pos", "y_pos", "elapsed_time"]

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



	# this is here just to satisfy the requirements of the graphical interface
	# x_pos_start = FloatParameter("X Start Position", units="m", default=0.)
	# x_pos_end = FloatParameter("X End Position", units="m", default=2.)
	# x_pos_step = FloatParameter("X Scan Step Size", units="m", default=0.1)
	# y_pos_start = FloatParameter("Y Start Position", units="m", default=-1.)
	# y_pos_end = FloatParameter("Y End Position", units="m", default=1.)
	# y_pos_step = FloatParameter("Y Scan Step Size", units="m", default=0.1)


	delay = FloatParameter("Step Delay: ", default = 0.1)

	x_axis = 1
	y_axis = 2


	def startup(self):
		log.info("Connecting and configuring the instruments")

		if self.fast_slow == "x / y":
			fast = self.x_axis
			slow = self.y_axis
		else:
			fast = self.y_axis
			slow = self.x_axis


		self.lockin = DSP7265("GPIB::12")

		self.stepper = ANC150("COM4")

		self.stepper.set_f(fast, self.fast_frequency)
		self.stepper.set_v(fast, self.fast_voltage)
		self.stepper.set_mode(fast, 'stp')

		self.stepper.set_f(slow, self.slow_frequency)
		self.stepper.set_v(slow, self.slow_voltage)
		self.stepper.set_mode(slow, 'stp')



	def execute(self):
		print(self.delay)

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



		# self.x_pos_step = self.forw_step
		# self.y_pos_step = self.delta_y_up
		# self.x_pos_start = 0
		# self.y_pos_start = 0
		# self.x_pos_end = self.total_x / self.delta_x_up
		# self.y_pos_end = self.total_y / self.delta_y_up

		start_time = time()
		# log.info("x freq " + str(self.stepper.get_f(self.x_axis)))
		# log.info("y freq " + str(self.stepper.get_f(self.y_axis)))

		# log.info("x voltage" + str(self.stepper.get_v(self.x_axis)))
		# log.info("y voltage" + str(self.stepper.get_v(self.y_axis)))
		# # log.info("tot x" + str(self.total_x))
		# log.info("tot y" + str(self.total_y))
		#
		# log.info("del x" + str(self.delta_x))
		# log.info("del y" + str(self.delta_y))
		#
		# log.info("x start" + str(self.x_start))
		# log.info("y start" + str(self.y_start))
		#total number of spots



		# if self.sweep_y:
		# 	sweep_total = self.total_y
		# 	sweep_delta_up = self.delta_y_up
		# 	sweep_delta_down = self.delta_y_down
		#
		# 	total = self.total_x
		# 	delta_up = self.delta_x_up
		# 	sweep_axis = self.y_axis
		# 	axis = self.x_axis
		#
		# else:
		# 	sweep_total = self.total_x
		# 	sweep_delta_up = self.delta_x_up
		# 	sweep_delta_down = self.delta_x_down
		#
		# 	total = self.total_y
		# 	delta_up = self.delta_y_up
		#
		# 	sweep_axis = self.x_axis
		# 	axis = self.y_axis

		num_progress = (self.forw_total/ self.forw_step ) * (self.slow_total / self.slow_step)
		log.info(str(num_progress))

		#forward = True

		for slow_progress in range(0, self.slow_total, self.slow_step):

			#log.info("x_progress")# + str(x_progress))
			for fast_forw_progress in range(0, self.forw_total, self.forw_step):
				log.info(str(fast_forw_progress))
				fast_pos =  fast_forw_progress / self.forw_step
				slow_pos = slow_progress / self.slow_step

				if self.fast_slow == "x / y":
					log.info("(x = " + str(fast_pos) + ", " + "(y = " + str(slow_pos))
					self.emit('results', {
						"X": self.lockin.x,
						"Y": self.lockin.y,
						"x_pos": fast_pos,
						"y_pos": slow_pos,
						"elapsed_time": time() - start_time
						})

				else:
					log.info("(x = " + str(slow_pos) + ", " + "(y = "+ str(fast_pos))
					self.emit('results', {
						"X": self.lockin.x,
						"Y": self.lockin.y,
						"x_pos": slow_pos,
						"y_pos": fast_pos,
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
