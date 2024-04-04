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


class XYScanProcedure(Procedure):

	"""
	Procedure for performing scans in the xy-plane with attocube ANC150
	"""
	queued_time = Parameter('Time Queued')

	sample_name = Parameter("Sample Name", default='')
	DATA_COLUMNS = ["X", "Y", "x_pos", "y_pos", "elapsed_time"]

	total_x = IntegerParameter("Total x:", default = 1)
	total_y = IntegerParameter("Total y:", default = 1)

	delta_x = IntegerParameter("Step size x:", default = 1)
	delta_y = IntegerParameter("Step size y:", default = 1)


	x_start = IntegerParameter("Offset x:", default = 0)
	y_start = IntegerParameter("Offset y:", default = 0)

	delay  = FloatParameter("Step Delay: ", default = 0.1)

	x_axis = 1
	y_axis = 2


	def startup(self):
		log.info("Connecting and configuring the instruments")

		self.lockin = DSP7265("GPIB::12")
		self.stepper = ANC150("COM4")

		self.stepper.set_f(self.x_axis, 1000)
		self.stepper.set_v(self.x_axis, 35)
		self.stepper.set_mode(self.x_axis, 'stp')

		self.stepper.set_f(self.y_axis, 1000)
		self.stepper.set_v(self.y_axis, 32)
		self.stepper.set_mode(self.y_axis, 'stp')

	def execute(self):
		print(self.delay)

		if self.x_start > 0:
			for i in range(0, self.x_start, self.delta_x):
				self.stepper.stepu(x_axis, self.delta_x)
				sleep(self.delay)
				log.info("x start up")
		else:
			for i in range(0, -1 * self.x_start, self.delta_x):
				self.stepper.stepd(x_axis, self.delta_x)
				sleep(self.delay)
				log.info("x start down")
				
		if self.y_start > 0:
			for i in range(0, self.y_start, self.delta_y):
				self.stepper.stepu(y_axis, self.delta_y)
				sleep(self.delay)
				log.info("y start up")
		else:
			for i in range(0, -1 * self.y_start, self.delta_y):
				self.stepper.stepd(y_axis, self.delta_y)
				sleep(self.delay)
				log.info("y start down")


		start_time = time()
		log.info("tot x" + str(self.total_x))
		log.info("tot y" + str(self.total_y))

		log.info("del x" + str(self.delta_x))
		log.info("del y" + str(self.delta_y))

		log.info("x start" + str(self.x_start))
		log.info("y start" + str(self.y_start))
		#total number of spots
		num_progress = (self.total_x / self.delta_x) * (self.total_y / self.delta_y)
		log.info(str(num_progress))

		forward = True

		for y_progress in range(0, self.total_y, self.delta_y):

			#log.info("x_progress")# + str(x_progress))
			for x_progress in range(0, self.total_x, self.delta_x):




				if forward == True:
					self.stepper.stepu(self.x_axis, self.delta_x)
					log.info("x up" + str(x_progress))
				else:
					self.stepper.stepd(self.x_axis, self.delta_x)
					log.info("x down" + str(x_progress))

				progress = (y_progress / self.delta_y * self.total_x /self.delta_x) + x_progress / self.delta_x

				self.emit("progress", int(100*progress / num_progress))
				sleep(self.delay)
				log.info("Recording results")

				if forward:
					x_pos = x_progress / self.delta_x
				else:
					x_pos = (self.total_x / self.delta_x) - (x_progress / self.delta_x) - 1

				y_pos = y_progress / self.delta_y

				self.emit('results', {
					"X": self.lockin.x,
                	"Y": self.lockin.y,
					"x_pos": x_pos,
					"y_pos": y_pos,
					"elapsed_time": time() - start_time
					})
				if self.should_stop():
					log.warning("Caught stop flag in procedure.")
					break

			self.stepper.stepu(self.y_axis, self.delta_y)
			forward  = not forward
			log.info("y up" + str(y_progress))

	def shutdown(self):
		self.stepper.shut_down()
