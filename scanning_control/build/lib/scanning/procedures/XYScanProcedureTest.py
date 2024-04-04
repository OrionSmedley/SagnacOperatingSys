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


class XYScanProcedureTest(Procedure):

	"""
	Procedure for performing scans in the xy-plane with attocube ANC150
	"""
	queued_time = Parameter('Time Queued')

	sample_name = Parameter("Sample Name", default='')
	DATA_COLUMNS = ["X", "Y", "x_pos", "y_pos", "elapsed_time"]

	x_start = IntegerParameter("Offset x:", default = 0)
	y_start = IntegerParameter("Offset y:", default = 0)

	total_x = IntegerParameter("Total x:", default = 1)
	total_y = IntegerParameter("Total y:", default = 1)

	delta_x_up = IntegerParameter("Step size x up:", default = 1)
	delta_x_down = IntegerParameter("Step size x down", default = 1)

	delta_y_up = IntegerParameter("Step size y up:", default = 1)
	delta_y_down = IntegerParameter("Step size y down:", default = 1)

	voltage_x = IntegerParameter("x voltage: ", default = 35)
	voltage_y = IntegerParameter("y voltage: ", default = 35)

	frequency_x = IntegerParameter("x frequency: ", default = 1000)
	frequency_y = IntegerParameter("y frequency: ", default = 1000)

	# this is here just to satisfy the requirements of the graphical interface
	x_pos_start = FloatParameter("X Start Position", units="m", default=0.)
	x_pos_end = FloatParameter("X End Position", units="m", default=2.)
	x_pos_step = FloatParameter("X Scan Step Size", units="m", default=0.1)
	y_pos_start = FloatParameter("Y Start Position", units="m", default=-1.)
	y_pos_end = FloatParameter("Y End Position", units="m", default=1.)
	y_pos_step = FloatParameter("Y Scan Step Size", units="m", default=0.1)

	sweep_y = BooleanParameter("Sweep in y", default = False)

	delay = FloatParameter("Step Delay: ", default = 0.1)

	x_axis = 1
	y_axis = 2


	def startup(self):
		log.info("Connecting and configuring the instruments")


		self.lockin = DSP7265("GPIB::12")

		self.stepper = ANC150("COM4")

		self.stepper.set_f(self.x_axis, self.frequency_x)
		self.stepper.set_v(self.x_axis, self.voltage_x)
		self.stepper.set_mode(self.x_axis, 'stp')

		self.stepper.set_f(self.y_axis, self.frequency_y)
		self.stepper.set_v(self.y_axis, self.voltage_y)
		self.stepper.set_mode(self.y_axis, 'stp')



	def execute(self):
		print(self.delay)

		if self.x_start > 0:
		 	for i in range(0, self.x_start, self.delta_x_up):
		 		self.stepper.stepu(self.x_axis, self.delta_x_up)
		 		sleep(self.delay)
				#log.info("x start up")
		else:
			for i in range(0, -1 * self.x_start, self.delta_x_up):
				self.stepper.stepd(self.x_axis, self.delta_x_up)
				sleep(self.delay)
				log.info("x start down")

		if self.y_start > 0:
			for i in range(0, self.y_start, self.delta_y_up):
				self.stepper.stepu(self.y_axis, self.delta_y_up)
				sleep(self.delay)
				log.info("y start up")
		else:
			for i in range(0, -1 * self.y_start, self.delta_y_up):
				self.stepper.stepd(self.y_axis, self.delta_y_up)
				sleep(self.delay)
				log.info("y start down")



		self.x_pos_step = self.delta_x_up
		self.y_pos_step = self.delta_y_up
		self.x_pos_start = 0
		self.y_pos_start = 0
		self.x_pos_end = self.total_x / self.delta_x_up
		self.y_pos_end = self.total_y / self.delta_y_up

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



		if self.sweep_y:
			sweep_total = self.total_y
			sweep_delta_up = self.delta_y_up
			sweep_delta_down = self.delta_y_down

			total = self.total_x
			delta_up = self.delta_x_up
			sweep_axis = self.y_axis
			axis = self.x_axis

		else:
			sweep_total = self.total_x
			sweep_delta_up = self.delta_x_up
			sweep_delta_down = self.delta_x_down

			total = self.total_y
			delta_up = self.delta_y_up

			sweep_axis = self.x_axis
			axis = self.y_axis

		


		num_progress = (self.total_x / self.delta_x_up) * (self.total_y / self.delta_y_up)
		log.info(str(num_progress))

		forward = True





		for progress in range(0, total, delta_up):

			#log.info("x_progress")# + str(x_progress))
			for sweep_progress in range(0, sweep_total, sweep_delta_up):

				if self.sweep_y:
					if forward:
						y_pos =  sweep_progress / sweep_delta_up
					else:
						y_pos = (sweep_total/ sweep_delta_up) - (sweep_progress / sweep_delta_up) - 1

					x_pos = progress / delta_up
				else:
					if forward:
						x_pos =  sweep_progress / sweep_delta_up
					else:
						x_pos = (sweep_total/ sweep_delta_up) - (sweep_progress / sweep_delta_up) - 1

					y_pos = progress / delta_up

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

				if forward == True:
					self.stepper.stepu(sweep_axis, sweep_delta_up)
					log.info("sweep axis up" + str(sweep_progress))
				else:
					self.stepper.stepd(sweep_axis, sweep_delta_down)
					log.info("sweep axis down" + str(sweep_progress))

				complete = (progress / delta_up * sweep_total/sweep_delta_up) + sweep_progress / sweep_delta_up

				self.emit("progress", int(100*complete / num_progress))
				sleep(self.delay)
				log.info("Recording results")



			self.stepper.stepu(axis, delta_up)
			forward  = not forward
			log.info("non-sweep axis up" + str(progress))
			if self.should_stop():
				log.warning("Caught stop flag in procedure.")
				break





	def shutdown(self):
		self.stepper.shut_down()
