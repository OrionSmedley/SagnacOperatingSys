import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
import os
from datetime import datetime
import textwrap

import numpy as np

from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow, ManagedImageWindow
from pymeasure.experiment import Results, unique_filename
# from pymeasure.instruments.attocube import ANC150
from scanning import ANC150
from scanning.procedures import ZScanProcedure

import send_gmail

class ZScanProcedureGUI(ManagedWindow):

	def __init__(self):
		super(ZScanProcedureGUI, self).__init__(
			procedure_class=ZScanProcedure,
			displays=[
				'sample_name',
				'z_start',
				'z_step',
				],
			x_axis='X',
			y_axis='z',
			#z_axis = 'X'
		)
		self.setWindowTitle('Z Scan')
		self.last_series_fname = None

	def _setup_ui(self):
		"""
		Loads custom QT UI for montana AMR measurements
		"""
		super(ZScanProcedureGUI, self)._setup_ui()
		self.inputs.hide()
		self.run_directory = os.path.dirname(os.path.realpath(__file__))
		self.inputs = fromUi(os.path.join(self.run_directory,
										  'gui_ZScan.ui'))

	def make_procedure(self):
		"""
		Constructs a single procedure
		"""
		procedure = ZScanProcedure()
		procedure.sample_name = self.inputs.sample_name.text()

		procedure.z_start = self.inputs.z_start.value()

		procedure.z_total = self.inputs.z_total.value()

		procedure.z_step = self.inputs.z_step.value()

		procedure.delay = self.inputs.delay.value()*1e-3 # ms

		procedure.z_voltage = self.inputs.z_voltage.value()
		procedure.z_frequency = self.inputs.z_frequency.value()


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
		suf = '_ZScan'
		series_fname = unique_filename(self.inputs.save_dir.text(),prefix=pre,
									   suffix=suf,dated_folder=True,ext='txt')

		series_header = '# Initial x: %.5f T\n'%self.inputs.z_start.value()
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
			suf = '_ZScan_xt%d'%procedure.z_total
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
	window = ZScanProcedureGUI()
	window.show()
	sys.exit(app.exec_())
