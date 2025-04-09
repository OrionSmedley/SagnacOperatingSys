from time import sleep, time
import sys
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np


import os
from datetime import datetime
import textwrap


from pymeasure.log import console_log
from pymeasure.display.Qt import QtCore, QtGui, fromUi
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import Results, unique_filename
import pyvisa as pv


#from ..custom_instruments import kavliRotatingMagnet
#from pymeasure.instruments.signalrecovery import DSP7265
#from pymeasure.instruments.agilent import Agilent8257D
from pymeasure.instruments.lakeshore import LakeShore331
from pymeasure.instruments.keithley import Keithley2400
from pymeasure.instruments.keithley import Keithley2182A
from pymeasure.experiment import Procedure
from pymeasure.experiment import Parameter, FloatParameter, BooleanParameter

class Nonlocal(Procedure):

    sample_name = Parameter("Sample Name", default='')

    average_time = FloatParameter("Average time", default=10)
    #average_times = np.arange(average_time)

    repeat_time = FloatParameter("Repeat time", default=10)

    #repeat_times = np.arange(repeat_time)

    delay = FloatParameter("Delay", units="ms", default=500)
    voltage_compliance = FloatParameter("Compliance", units="v", default=0.5)
    applied_current = FloatParameter("Current", units="uv", default=50)


    temperature = FloatParameter("temperature Setpoint", units="K", default=20.)
    control_temp = BooleanParameter("Automatically Change Setpoint", default=False)
    equilibration_time = FloatParameter("Temp Equilibration Time", units="s", default=1800.)

    first = True
    last = True

    DATA_COLUMNS = ["elapsed_time","temperature", "voltage","numbers","measured_current"]

    def startup(self):
        log.info("Connecting and configuring the instruments")

        #self.tempcontroller = LakeShore331("GPIB::12")

        self.sourcemeter = Keithley2400("GPIB::14")
        #self.sourcemeter.reset()
        self.sourcemeter.apply_current()
        self.sourcemeter.compliance_voltage=self.voltage_compliance
        self.sourcemeter.source_current=0
        self.sourcemeter.enable_source()
        #self.sourcemeter.current

        self.voltmeter = Keithley2182A("GPIB::3")
        self.voltmeter.set_voltage_mode()
        self.voltmeter.rate=1
        self.voltmeter.enable_low_pass_filter()

    def execute(self):
        # Change temp setpoint if requested
        # if self.first and self.control_temp:
        #     self.tempcontroller.setpoint_1 = self.temperature
        #     self.tempcontroller.wait_for_temperature(timeout=1800,accuracy=1)
        #     log.info('Temp reached waiting for %g seconds' % self.equilibration_time)
        #     equil_start_time = time()
        #     while (time() - equil_start_time) < self.equilibration_time:
        #         sleep(1)
        #         if self.should_stop():
        #             break

        start_time = time()

        repeat_time=int(self.repeat_time)
        average_time=int(self.average_time)
    
        for rtimes in range (repeat_time):

            FALIURE_LIMIT = 10
            faliure_counter = 0
            success = False
            while faliure_counter < FALIURE_LIMIT:
                try:
                    self.sourcemeter.source_current=self.applied_current*((-1)**rtimes)
                    log.info(self.voltmeter.voltage)
                    log.info('Runing in cycle %g' %rtimes)
                    self.emit("progress", int(100*rtimes/self.repeat_time))
                    sleep(self.delay)
                    log.info("Recording results")

                    for atime in range (average_time):
                        sleep(0.05)
                        data = {
                        #"applied_currents": self.applied_current*((-1)**rtimes),
                        "elapsed_time": time()-start_time,
                        #"real_temperature": self.tempcontroller.temperature_A,
                        "temperature": self.temperature,
                        "measured_current": self.sourcemeter.current[1],
                        "voltage": self.voltmeter.voltage,
                        "numbers": atime
                        }
                        self.emit('results', data)

                    if self.should_stop():
                        log.warning("Caught stop flag in procedure.")
                        break
                except pv.errors.VisaIOError:
                    faliure_counter += 1
                    log.warning("failed, at count {count} of {max}".format(
                        count=faliure_counter,
                        max=FALIURE_LIMIT
                        )
                    )
                    continue
                success = True # only runs if we beat try statement
                break
            if not success:
                 raise RuntimeError("Not able to successfully communicate with Keithley 2400")
        

    def shutdown(self):
        if self.last or self.should_stop():
            log.info("Finished with scans. Shutting down instruments.")
            self.sourcemeter.shutdown()
        else:
            log.info("Done with one scan, but more to go.")

class MainWindow(ManagedWindow):

    def __init__(self):
        super(MainWindow, self).__init__(
            procedure_class=Nonlocal,
            #displays=['temperature'],
            x_axis='elapsed_time',
            y_axis='voltage'
        )
        self.setWindowTitle('nonlocal')

    def _setup_ui(self):
        super(MainWindow, self)._setup_ui()
        self.inputs.hide()
        self.run_directory = os.path.dirname(os.path.realpath(__file__))
        self.inputs = fromUi(os.path.join(self.run_directory,
                                          'custom_inputs/kavli_gui_nonlocalDC.ui'))
    def queue (self):
        

        #directory = self.inputs.folder.text()
        #filename = unique_filename(directory, prefix=self.inputs.sample_name.text(), ext='txt', datetimeformat='')



        sname = self.inputs.sample_name.text()
        pre = sname+ '_'+str(self.inputs.temp_setpoint.value())+'_K_rate1_cycle_'+str(self.inputs.repeat.value())+'_average_'+str(self.inputs.average.value())+'_sleep_'+str(self.inputs.delay.value()*0.001)+'_Current_%0.1f_uA'%(self.inputs.applied_current.value())
        filename = unique_filename(self.inputs.folder.text(), prefix=pre, ext='csv', datetimeformat='')

       # C:/Users/Kavli/Desktop/Tianxiang/Tests/empty_0nm_56_23_'+str(T)+'_K_rate1_cycle_'+str(times)+'_average_'+str(averageP)+'_sleep_'+str(delay)+'_Current_%0.1f_uA.csv'%(Ip*1e6)

        procedure = Nonlocal()
        procedure.applied_current = self.inputs.applied_current.value()*1e-6

        procedure.voltage_compliance = self.inputs.compliance.value()
        procedure.delay = self.inputs.delay.value()*0.001
        procedure.average_time = self.inputs.average.value()
        procedure.repeat_time = self.inputs.repeat.value()

        procedure.temperature = self.inputs.temp_setpoint.value()
        procedure.control_temp = self.inputs.control_temp.isChecked()
        procedure.equilibration_time = self.inputs.temp_eq_time.value() if procedure.control_temp else 0.

        results = Results(procedure, filename)
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())