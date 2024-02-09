import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import sys
from pymeasure.log import console_log
from pymeasure.experiment import Results, unique_filename

from pymeasure.instruments.zurich import HF2LI
from ..custom_instruments import daedalusProjField
from pymeasure.instruments.keithley import Keithley6221, Keithley2000
from pymeasure.experiment import Procedure
from pymeasure.experiment import IntegerParameter, FloatParameter, BooleanParameter, Parameter
from pymeasure.adapters import DAQmxAdapter
from time import sleep, time
from scipy import special
import numpy as np

class sagnacOpticsXportMCDProcedure(Procedure):
	"""
	Procedure for taking Heterodyne Hysteresis Measurements 
	with the Sagnac setup
	"""

	calib_file = 'C:\\Users\\Ralph Group\\Desktop\\git\\sagnac_control\\calibrations\\sagnac'
	sample_name = Parameter("Sample Name",default='test')

	applied_voltage = FloatParameter("Applied Sample Voltage", units="V", default=1)
	# apply_current = BooleanParameter("Current Applied?", default=True)
	# current_amplitude = FloatParameter("Applied Sample Current Amplitude", units="A", default=1)
	current_frequency = FloatParameter("Applied Sample Current frequency", units="kHz", default=1)
	# current_offset = FloatParameter("Applied Sample Current offset", units="A", default=1)
	settling = FloatParameter("Settling", units="s", default=0.5)
	wait = FloatParameter("Pre Measurement Wait Time", units="s", default=0.5)
	avgs = IntegerParameter("Number of Averages", default = 1)
	amp_gain = FloatParameter("Amp Gain", units="x", default=1)

	saturate = BooleanParameter("Saturate First?", default=True)
	saturating_field = FloatParameter("Saturating Magnetic Field", units="T", default=0.1)
	saturating_field_azimuth = FloatParameter("Saturating Magnetic Field Azimuth", units="deg", default=0.)
	saturating_field_polar = FloatParameter("Saturating Magnetic Field Polar", units="deg", default=90.0)

	hysteresis = BooleanParameter("Hysteresis Sweep?", default=True)
	reverse = BooleanParameter("Reverse?", default=False)
	sweep_field = FloatParameter("Bias Magnetic Field", units="T", default=0.1)
	sweep_field_step = FloatParameter("Bias Magnetic Field step", units="T", default=0.1)
	sweep_field_azimuth = FloatParameter("Bias Magnetic Field Azimuth", units="deg", default=0.)
	sweep_field_polar = FloatParameter("Bias Magnetic Field Polar", units="deg", default=0.0)

	apply_bias_field = BooleanParameter("Apply a Bias Field?", default = False)
	bias_field_x = FloatParameter("Bias Field x", units="T", default=0)
	bias_field_y = FloatParameter("Bias Field y", units="T", default=0)
	bias_field_z = FloatParameter("Bias Field z", units="T", default=0)

	input_range = FloatParameter("input range", units="V", default=1)
	imp50 = BooleanParameter("50 Ohm Input Impedance", default=True)

	f_eom = FloatParameter("EOM Frequency", units="MHz", default=1)

	first_harm_order = IntegerParameter("Filter Order First Harmonic", default=4)
	second_harm_order = IntegerParameter("Filter Order Second Harmonic", default=4)
	first_harm_tc = FloatParameter("Lockin Time Constant First Harmonic", units="s", default=0.1)
	second_harm_tc = FloatParameter("Lockin Time Constant Second Harmonic", units="s", default=0.1)

	eom_voltage = FloatParameter("Output Voltage", units="V", default=1)
	queued_time = Parameter('Time Queued')

	first = True
	last = True

	DATA_COLUMNS = ["ThetaK", "MCD", "X0", "X1","Y1","X2","Y2","DeltaThetaK","DeltaX1","DeltaY1","TX1","TY1","TX2","TY2","sweep_field","elapsed_time"]

	def startup(self):
		log.info("Connecting and configuring the instruments")

		log.info("Connecting to the multimeter")
		self.keithley = Keithley2000("GPIB::5")
		self.keithley.measure_voltage()

		log.info("Connecting to the magnet")
		self.magnet = daedalusProjField(DAQmxAdapter('Dev1', ['ao0', 'ai1']),"GPIB::10")
		self.magnet.load_calibration_params(self.calib_file)

		log.info("Connecting to the Zurich Lock-in")
		self.lockin = HF2LI(8005,1,1004)
		self.lockin.set_vout(1,0,self.applied_voltage/10*np.sqrt(2))
		#subscribe to outputs
		self.lockin.sub(0)
		self.lockin.sub(1)
		# self.lockin.sub(2)
		self.lockin.sub(3)
		self.lockin.sub(4)
		self.lockin.sub(5)

		self.apply_bias_field = False
		if self.bias_field_x != 0 or self.bias_field_y != 0 or self.bias_field_z != 0:
			self.apply_bias_field = True

	def execute(self):
		J2J1 = 0.543
		J1J0 = 1.837
		deg2rad = np.pi/180.
		field_points = np.arange(0,
								 self.sweep_field,
								 self.sweep_field_step)
		if self.sweep_field not in field_points:
			field_points = np.append(field_points,self.sweep_field)
		
		field_points = field_points[::-1]

		field_points = np.append(field_points,
								 -1*field_points[::-1][1:])
		if self.hysteresis:                        
			field_points = np.append(field_points, field_points[::-1][1:])

		if self.reverse:
			field_points = field_points[::-1]
		
		if self.saturate:
			# ensure we have gotten to the phi we want
			while not np.isclose(self.magnet.phi, self.saturating_field_azimuth, atol=1e-3):
				log.info(f"setting magnet azimuthal orientation to {self.saturating_field_azimuth} deg")
				self.magnet.phi = self.saturating_field_azimuth
				while self.magnet.in_motion: # wait for all motion to finish
					sleep(0.1)
				for err in self.magnet.errors:
					log.warning('%s'%err)
			# NOTE: in the future will probably want to check that we have actually reached
			# the theta value we set it to.
			log.info(f"setting magnet polar orientation to {self.saturating_field_polar} degrees")
			self.magnet.theta = self.saturating_field_polar
			nom_x, _, _ = self.magnet.angle_calibration(self.saturating_field_polar, self.saturating_field_azimuth) #temporary fix for bad x axis
			att = 1
			while not np.isclose(self.magnet.motion_inst.x.position, nom_x, atol=1e-3): #temporary fix for bad x axis
				self.magnet.motion_inst.x.enable()
				self.magnet.motion_inst.x.position = nom_x
				sleep(0.1)
				while self.magnet.in_motion: # wait for all motion to finish
					sleep(0.1)
				for err in self.magnet.errors:
					log.warning('%s'%err)
				att = att + 1
				log.info(f"attempt number {att}")
				
			while self.magnet.in_motion: # wait for all motion to finish
				sleep(0.1)
			for err in self.magnet.errors:
				log.warning('%s'%err)
			log.info("Setting the Saturating Field")
			self.magnet.set_vector_field(self.saturating_field,
										 phi=self.saturating_field_azimuth, 
										 theta=self.saturating_field_polar)
			log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")
			sleep(self.settling)

			self.magnet.volts = 0
		
		if not self.apply_bias_field:
			# ensure we have gotten to the phi we want
			while not np.isclose(self.magnet.phi, self.sweep_field_azimuth, atol=1e-3):
				log.info(f"setting magnet azimuthal orientation to {self.sweep_field_azimuth} deg")
				self.magnet.phi = self.sweep_field_azimuth
				while self.magnet.in_motion: # wait for all motion to finish
					sleep(0.1)
				for err in self.magnet.errors:
					log.warning('%s'%err)
			# NOTE: in the future will probably want to check that we have actually reached
			# the theta value we set it to.
			log.info(f"setting magnet polar orientation to {self.sweep_field_polar} degrees")
			self.magnet.theta = self.sweep_field_polar
			nom_x, _, _ = self.magnet.angle_calibration(self.sweep_field_polar, self.sweep_field_azimuth) #temporary fix for bad x axis
			att = 1
			while not np.isclose(self.magnet.motion_inst.x.position, nom_x, atol=1e-3): #temporary fix for bad x axis
				self.magnet.motion_inst.x.enable()
				self.magnet.motion_inst.x.position = nom_x
				sleep(0.1)
				while self.magnet.in_motion: # wait for all motion to finish
					sleep(0.1)
				for err in self.magnet.errors:
					log.warning('%s'%err)
				att = att + 1
				log.info(f"attempt number {att}")
			while self.magnet.in_motion: # wait for all motion to finish
				sleep(0.1)
			for err in self.magnet.errors:
				log.warning('%s'%err)
			log.info("Setting Sweep Field")
			self.magnet.field = field_points[0]
			log.info(f"Magnet is at {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")

		else:
			self.magnet.set_cart_vector_field(field_points[0]*np.cos(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_x,
											  field_points[0]*np.sin(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_y,
											  field_points[0]*np.sin(self.sweep_field_polar*deg2rad) + self.bias_field_z)
			while self.magnet.in_motion: # wait for all motion to finish
				sleep(0.1)
			for err in self.magnet.errors:
				log.warning('%s'%err)

		while self.magnet.in_motion: # wait for all motion to finish
			sleep(0.1)
		for err in self.magnet.errors:
			log.warning('%s'%err)
		
		log.info("Waiting a while to equilibrate")
		sleep(self.wait)

		num_progress = field_points.size
		start_time = time()

		for progress_iterator, field in enumerate(field_points):
			self.emit("progress", 100*progress_iterator/num_progress)
			if not self.apply_bias_field:
				self.magnet.field = field
				log.info(f"Setting Magnetic Field to {field:.5f} T")
			else:
				Bx = field*np.cos(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_x
				By = field*np.sin(self.sweep_field_azimuth*deg2rad)*np.cos(self.sweep_field_polar*deg2rad) + self.bias_field_y
				Bz = field*np.sin(self.sweep_field_polar*deg2rad) + self.bias_field_z
				self.magnet.set_cart_vector_field(Bx,By,Bz)
				log.info(f"Setting magnetic field (Cartesian) to {Bx:.4f},{By:.4f},{Bz:.4f}")
				while self.magnet.in_motion: # wait for all motion to finish
					sleep(0.1)
				for err in self.magnet.errors:
					log.warning('%s'%err)
				log.info(f"This corresponds to location {self.magnet.motion_inst.x.position:.2f},{self.magnet.motion_inst.y.position:.2f},{self.magnet.motion_inst.phi.position:.2f}")

			while self.magnet.in_motion: # wait for all motion to finish
				sleep(0.1)
			for err in self.magnet.errors:
				log.warning('%s'%err)
			
			dat_list = []
			X0_list = []
			for i in range(self.avgs):
				self.lockin.sync() # clears buffer since field has changed
				sleep(self.settling)
				self.lockin.sync() # clears buffer since field has changed
				log.info("recording average #%d"%i)
				dat_list.append(self.lockin.poll_and_unpack(0.02, 100, [0,1,3,4,5], ['x','y'], ratio=False))
				X0_list.append(self.keithley.voltage)
			dat = {i : {comp : sum(dat_list[j][i][comp] for j in range(len(dat_list)))/len(dat_list) for comp in dat_list[0][i].keys()} for i in dat_list[0].keys()}

			X0 = sum(X0_list)/len(X0_list)
			phim = 0.92
			J0 = special.jv(0,2*phim)
			J1 = special.jv(1,2*phim)
			J2 = special.jv(2,2*phim)

			log.info("Recording results")
			self.emit('results', {
				"ThetaK": np.arctan(J2J1*dat[3]['x']/dat[5]['y'])/2, 
				"MCD": np.sqrt((X0 + dat[5]['y']*J0/J2  - np.sqrt(dat[3]['x']**2/J1**2 + dat[5]['y']**2/J2**2))) / np.sqrt ((X0 + dat[5]['y']*J0/J2  + np.sqrt(dat[3]['x']**2/J1**2 + dat[5]['y']**2/J2**2))),
				"X0": X0,
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
				"sweep_field": field,
				"elapsed_time": time()-start_time
				})
			if self.should_stop():
				log.warning("Caught stop flag in procedure.")
				break

	def shutdown(self):
		if self.last or self.should_stop():
			log.info("Finished with scans. Shutting down instruments.")
			# self.magnet.shutdown()
			self.magnet.volts = 0
			# if self.apply_current:
			#     self.source.shutdown()
		else:
			log.info("Finished with one scan, but more to go.")
			sleep(1)