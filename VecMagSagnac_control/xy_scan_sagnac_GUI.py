import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
import textwrap
from itertools import product
import socket

import numpy as np

from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow, ManagedImageWindow
from pymeasure.experiment import Results, unique_filename
# from pymeasure.instruments.attocube import ANC150
from scanning import ANC150
from sagnac.procedures import xy_scan_sagnac_procedure

#import send_gmail



class xy_scan_sagnac_GUI(ManagedWindow):

	def __init__(self):
		super(xy_scan_sagnac_GUI, self).__init__(
			procedure_class = xy_scan_sagnac_procedure,

			displays=[
				'sample_name'
				
				#'fast_slow',
				#'fast_start',
				#'slow_start',
				#'forw_total',
				#'back_total',
				#'slow_total',
				#'slow_return_total',
				#'forw_step',
				#'back_step',
				#'slow_step',
				#'slow_return_step'

				],
			#inputs = ['x_pos_start', 'x_pos_end', 'x_pos_step', 'y_pos_start', 'y_pos_end', 'y_pos_step', 'delay'],
			x_axis ='x_pos',
			y_axis ='y_pos'
		)
		self.setWindowTitle('XY Scan Sagnac')
		self.last_series_fname = None

	def _setup_ui(self):
		"""
		Loads custom QT UI for montana AMR measurements
		"""
		super(xy_scan_sagnac_GUI, self)._setup_ui()
		self.inputs.hide()
		self.run_directory = os.path.dirname(os.path.realpath(__file__))
		self.inputs = fromUi(os.path.join(self.run_directory,'xy_scan_sagnac_gui.ui'))

	def make_procedure(self):
		"""
		Constructs a single procedure
		"""
		procedure = xy_scan_sagnac_procedure()
		procedure.sample_name = self.inputs.sample_name.text()

		procedure.fast_start = self.inputs.fast_start.value()
		procedure.slow_start = self.inputs.slow_start.value()

		procedure.forw_total = self.inputs.forw_total.value()
		procedure.back_total = self.inputs.back_total.value()
		procedure.slow_total = self.inputs.slow_total.value()
		procedure.slow_return_total = self.inputs.slow_return_total.value()

		procedure.forw_step = self.inputs.forw_step.value()
		procedure.back_step = self.inputs.back_step.value()
		procedure.slow_step = self.inputs.slow_step.value()
		procedure.slow_return_step = self.inputs.slow_return_step.value()

		procedure.fast_voltage = self.inputs.fast_voltage.value()
		procedure.slow_voltage = self.inputs.slow_voltage.value()

		procedure.fast_frequency = self.inputs.fast_frequency.value()
		procedure.slow_frequency = self.inputs.slow_frequency.value()

		procedure.x_pos_start = 0
		procedure.y_pos_start = 0

		procedure.settling = self.inputs.settling.value()
		procedure.wait = self.inputs.wait.value()





		procedure.fast_slow = self.inputs.fast_slow.currentText()

		
		procedure.delay = self.inputs.delay.value()*1e-3 # ms

		if procedure.fast_slow == "x / y":
			procedure.x_pos_end = procedure.forw_total - procedure.forw_step
			procedure.y_pos_end = procedure.slow_total - procedure.slow_step
			procedure.x_pos_step = procedure.forw_step
			procedure.y_pos_step = procedure.slow_step 
		else:
			procedure.y_pos_end = procedure.forw_total - procedure.forw_step
			procedure.x_pos_end = procedure.slow_total - procedure.slow_step
			procedure.y_pos_step = procedure.forw_step
			procedure.x_pos_step = procedure.slow_step




		procedure.queued_time = datetime.now().strftime("%I:%M%p %Y-%m-%d").lower()

		return procedure


	def make_procedures(self):
		"""
		Constructs a series of procedures based on gui options
		"""
		procedures = []

		procedures.append(self.make_procedure())

		return procedures

	def start_series(self):
		"""
		Creates the header and filename of the series file for these scans.
		"""
		pre = self.inputs.sample_name.text() if self.inputs.sample_name.text() else 'undefined'
		suf = '_XYScan'
		series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
									   suffix=suf,dated_folder=True,ext='txt')

		series_header = '# Initial fast: %.5f T\n'%self.inputs.fast_start.value()
		series_header += '# Initial slow: %.5f T\n'%self.inputs.slow_start.value()
		return series_fname, series_header

	def queue(self):
		direc = self.inputs.save_dir.text()
		# Make list of procedures
		procedures = self.make_procedures()


		for procedure in procedures:
			# ensure *some* sample name exists so Results.load() works
			if procedure.sample_name == '':
				procedure.sample_name = 'undefined'

			# create files
			pre = procedure.sample_name + '_'
			suf = '_XYScan_forwt%d'%procedure.forw_total + '_slowt%d'%procedure.slow_total
			filename = unique_filename(direc,dated_folder=True,suffix=suf,
										prefix=pre)
			#if do_sweep:
				#series_file.write(os.path.split(filename)[-1] + '\n')

			# Queue experiment
			results = Results(procedure,filename)
			experiment = self.new_experiment(results)
			self.manager.queue(experiment)
		#if do_sweep:
			#series_file.close()

	def finished(self, experiment):
		super().finished(experiment)
		send_message = False
		if len(self.inputs.notify_email.text()) > 0:
			if self.inputs.notify_at_end.isChecked() or not self.manager.experiments.has_next():
				if not self.manager.experiments.has_next():
					send_message = True
					message = textwrap.dedent("""\
						There are no more queued AMR measurements on the montana setup.
						The last parameters ran were:

						Sample Name: %s

						Please update parameters or finish your measurement.
						""" % (experiment.procedure.sample_name))
			else:
				send_message = True
				message = textwrap.dedent("""\
					The scan has finished. The parameters of this scan
					were:

					Sample Name: %s

					""" % (experiment.procedure.sample_name))
		if send_message:
			subject = '[AMR Angle] Measurement finished on montana Setup'
			addresses = [str(self.inputs.notify_email.text())]
			files = []
			if self.last_series_fname is not None: # attach sweep file if appropriate
				files.append(self.last_series_fname)
			send_gmail('cornell.fmr', 'getingetin', addresses, subject, message, files)

if __name__ == '__main__':
	app = QtGui.QApplication(sys.argv)
	window = xy_scan_sagnac_GUI()
	window.show()
	sys.exit(app.exec_())
