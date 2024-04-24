
class ExperimentSettings:
    def __init__(self):
        self.amp_gain = 0
        self.applied_sample_voltage = 0
        self.applied_sample_voltage_offset = 0
        self.apply_bias_field = False
        self.number_of_averages = 1
        self.bias_field_x = 0
        self.bias_field_y = 0
        self.bias_field_z = 0
        self.applied_sample_current_frequency = "3.273 kHz"
        self.output_voltage = 0.65
        self.eom_frequency = 3.34762e+06  # MHz
        self.filter_order_first_harmonic = 8
        self.lockin_time_constant_first_harmonic = 0.01  # seconds
        self.hysteresis_sweep = True
        self.input_impedance_50_ohm = False
        self.input_range = 0.8  # volts
        self.keithley_voltage = 0
        self.time_queued = "12:27pm 2024-04-12"  # time stamp
        self.reverse = False
        self.sample_name = "LAFO"
        self.saturate_first = False
        self.filter_order_second_harmonic = 8
        self.lockin_time_constant_second_harmonic = 0.01  # seconds
        self.settling = 0.1  # seconds
        self.field_coils = {
            "saturating_magnetic_field": 0.17,  # tesla
            "saturating_magnetic_field_azimuth": 135,  # degrees
            "saturating_magnetic_field_polar": 90,  # degrees
            "bias_magnetic_field_azimuth": 135,  # degrees
            "bias_magnetic_field_polar": 90,  # degrees
            "bias_magnetic_field_start": -0.18,  # tesla
            "bias_magnetic_field_step": 0.01,  # tesla
            "bias_magnetic_field_stop": 0.18  # tesla
        }
        self.keithly = {
            "use_keithley": False,
            "pre_measurement_wait_time": 0  # seconds
        }
    
    def update_setting(self, setting, value):
        """ Generic method to update settings. """
        if hasattr(self, setting):
            setattr(self, setting, value)
        else:
            raise AttributeError(f"Setting '{{setting}}' not found in ExperimentSettings class.")
