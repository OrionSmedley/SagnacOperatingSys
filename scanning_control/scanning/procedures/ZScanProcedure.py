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


class ZScanProcedure(Procedure):

	"""
	Procedure for performing scans in the xy-plane with attocube ANC150
	"""
	queued_time = Parameter('Time Queued')

	sample_name = Parameter("Sample Name", default='')
	DATA_COLUMNS = ["X", "z_pos", "elapsed_time"]

	z_total = IntegerParameter("Total steps: ", default = 100)
	z_step = IntegerParameter("Step size: ", default = 1)

	z_voltage = IntegerParameter("Voltage: ", default = 35)
	z_frequency = IntegerParameter("Frequency: ", default = 1000)

	z_start = IntegerParameter("Offset: ", default = 0)

	z_axis = 3

	delay = FloatParameter("Step Delay: ", default = 0.1)


	def startup(self):
		log.info("Connecting and configuring the instruments")




		self.lockin = DSP7265("GPIB::12")

		self.stepper = ANC150("COM4")
		self.stepper.set_v(self.z_axis, self.z_voltage)
		self.stepper.set_f(self.z_axis, self.z_frequency)

		self.stepper.set_mode(self.z_axis, 'stp')



	def execute(self):
		print(self.delay)


		self.stepper.stepd(self.z_axis, 20000)
		sleep(self.delay)

		start_time = time()

		for start_progress in range(0, self.z_start, self.z_step):
			self.stepper.stupu(self.z_axis, self.z_step)
			sleep(self.delay)

		num_progress = (self.z_total / self.z_step)
		log.info(str(num_progress))

		#forward = True

		zs = []
		Xs = []



		for progress in range(0, self.z_total, self.z_step):
			z_pos = progress / self.z_total
			zs.append(z_pos)
			Xs.append(self.lockin.x)

			self.emit('results', {
				"X": self.lockin.x,
				"Y": self.lockin.y,
				"z_pos": fast_pos,
				"elapsed_time": time() - start_time
			})


			self.emit("progress", int(100*complete / num_progress))
			sleep(self.delay)
			log.info("Recording results")
			if self.should_stop():
				log.warning("Caught stop flag in procedure.")
				break


		if self.z_total != 0:
			zs = np.array(zs)
			Xs = np.array(Xs)
			max = np.argmax(Xs)
			log.info("Maximum voltage position: " + str(zs[max]))
			log.info("Maximum voltage: " + str(Xs[max]))

	def shutdown(self):
		self.stepper.shut_down()
