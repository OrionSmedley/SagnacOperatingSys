from PyQt5 import QtWidgets, uic, QtCore
import time
import sys
import os
import re
import random

try:
    from sagnacMultitool.aparatus.drivers.RenSciStack import RenSciStepper 
except ImportError:
    print("Could not import RenSciStepper module")
    quit()

class MyApp(QtWidgets.QDialog): 
    def __init__(self):
        super().__init__()

        #used for testing on kyle's laptop modifiable to whoever wants
        # uic.loadUi("c:/Users/05kyl/Downloads/SagnacOperatingSys/SagnacOperatingSys/MinimalSagnac/Drivers for cryostat.ui", self)
        
        uic.loadUi("D:/SagnacOperatingSys/MinimalSagnac/Drivers for cryostat.ui", self)
        #to edit the values for max of amp and volt have to use QTDesigner
        #used for RenSciStack conenction for amp and frequency/voltage
        self.stepper = RenSciStepper(host="169.254.62.189", port= 6002)
        self.stepper.connect()
        
        self.x_size = int(self.btn_Steps_x.value())
        self.y_size = int(self.btn_Steps_y.value())
        self.z_size = int(self.btn_Steps_z.value())
        
        self.stepper.voltage_x = 100
        self.stepper.voltage_y = 100
        self.stepper.voltage_z = 100
        
        self.stepper.frequency_x = 1000
        self.stepper.frequency_y = 1000
        self.stepper.frequency_z = 1000

        # Connect press/release signals
        
        self.btn_up.pressed.connect(lambda:self.stepper.step_y(step_size=self.y_size))
        self.btn_down.pressed.connect(lambda:self.stepper.step_y(step_size=-self.y_size))
        self.btn_left.pressed.connect(lambda:self.stepper.step_x(step_size=-self.x_size))
        self.btn_right.pressed.connect(lambda:self.stepper.step_x(step_size=self.x_size))
        self.btn_up_z.pressed.connect(lambda:self.stepper.step_z(step_size=self.z_size))
        self.btn_down_z.pressed.connect(lambda:self.stepper.step_z(step_size=-self.z_size))
        
        self.btn_stop.pressed.connect(lambda:self.stepper.stop())

        # ampliitude and volatage btns
        # sets values to whatever the curr val of ANC
        self.btn_Frequency_x.setValue(self.stepper.frequency_x) #x
        self.btn_Frequency_y.setValue(self.stepper.frequency_y) #y
        self.btn_Frequency_z.setValue(self.stepper.frequency_z) #z

        self.btn_Amplitude_x.setValue(self.stepper.voltage_x) #x
        self.btn_Amplitude_y.setValue(self.stepper.voltage_y) #y
        self.btn_Amplitude_z.setValue(self.stepper.voltage_z) #z
        
        # anytime a value is changed for freq or amp it updates
        self.btn_Frequency_x.valueChanged.connect(lambda val: self.stepper.set_frequency("x", val))
        self.btn_Frequency_y.valueChanged.connect(lambda val: self.stepper.set_frequency("y", val))
        self.btn_Frequency_z.valueChanged.connect(lambda val: self.stepper.set_frequency("z", val))

        self.btn_Amplitude_x.valueChanged.connect(lambda val: self.stepper.set_voltage("x", val))
        self.btn_Amplitude_y.valueChanged.connect(lambda val: self.stepper.set_voltage("y", val))
        self.btn_Amplitude_z.valueChanged.connect(lambda val: self.stepper.set_voltage("z", val))
        
        self.btn_target_x.valueChanged.connect(lambda val: self.stepper.target_positions.__setitem__("x", val))
        self.btn_target_y.valueChanged.connect(lambda val: self.stepper.target_positions.__setitem__("y", val))
        self.btn_target_z.valueChanged.connect(lambda val: self.stepper.target_positions.__setitem__("z", val))
        
        self.btn_Pos_check.pressed.connect(lambda:self.update_position_text())
        
        self.btn_send_to.pressed.connect(lambda:self.are_we_there_yet())

        # self.btn_ground.pressed.connect(self.stepper.stop())

        #continous btns

        self.pressed_keys = set()

        self.active_key = None

        self.move_timer = QtCore.QTimer()
        self.move_timer.timeout.connect(self.handle_slow_movement)
        self.move_timer.setInterval(100)  # slow stepping interval in ms
        
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFocus()

        self.setWindowTitle("Petasos")
        
    def are_we_there_yet(self):
        self.stepper.go_to_positions(self.stepper.target_positions)
        self.update_position_text()
        
    def update_position_text(self):
        positions = self.stepper.get_positions()

        text = (
            f"X: {positions["x"]:.3f} µm\n"
            f"Y: {positions["y"]:.3f} µm\n"
            f"Z: {positions["z"]:.3f} µm"
        )

        self.position_text.setPlainText(text)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return

        if not self.continous_check.isChecked():
            return

        key = event.key()

        valid_keys = {
            QtCore.Qt.Key_W,
            QtCore.Qt.Key_S,
            QtCore.Qt.Key_A,
            QtCore.Qt.Key_D,
            QtCore.Qt.Key_Z,
            QtCore.Qt.Key_X,
        }

        if key not in valid_keys:
            return

        # Avoid restarting motion if another key is already active
        if self.active_key is not None:
            return

        self.active_key = key

        if self.radioBtn_fast.isChecked():
            self.start_fast_continuous_motion(key)
        else:
            self.move_timer.start()

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return

        if event.key() != self.active_key:
            return

        self.active_key = None
        self.move_timer.stop()
        self.stepper.stop()
        self.update_position_text()

        print("All motion stopped")

    def start_fast_continuous_motion(self, key):
        if key == QtCore.Qt.Key_W:
            self.stepper.continuous_y(step_size=1)

        elif key == QtCore.Qt.Key_S:
            self.stepper.continuous_y(step_size=-1)

        elif key == QtCore.Qt.Key_A:
            self.stepper.continuous_x(step_size=-1)

        elif key == QtCore.Qt.Key_D:
            self.stepper.continuous_x(step_size=1)

        elif key == QtCore.Qt.Key_Z:
            self.stepper.continuous_z(step_size=1)

        elif key == QtCore.Qt.Key_X:
            self.stepper.continuous_z(step_size=-1)


    def handle_slow_movement(self):
        if self.active_key is None:
            return

        if not self.continous_check.isChecked():
            self.move_timer.stop()
            self.stepper.stop()
            self.active_key = None
            return

        if self.radioBtn_fast.isChecked():
            self.move_timer.stop()
            return

        key = self.active_key

        if key == QtCore.Qt.Key_W:
            self.stepper.step_y(step_size=self.y_size)

        elif key == QtCore.Qt.Key_S:
            self.stepper.step_y(step_size=-self.y_size)

        elif key == QtCore.Qt.Key_A:
            self.stepper.step_x(step_size=-self.x_size)

        elif key == QtCore.Qt.Key_D:
            self.stepper.step_x(step_size=self.x_size)

        elif key == QtCore.Qt.Key_Z:
            self.stepper.step_z(step_size=self.z_size)

        elif key == QtCore.Qt.Key_X:
            self.stepper.step_z(step_size=-self.z_size)

    def ground(self):
        self.stepper.stop() #ground all axis
        print("grounded")

    def closeEvent(self, event):
        # Automatically ground all axes when the window is closing
        self.stepper.stop()
        print("Axes grounded before closing.")
        event.accept()


if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())
