from PyQt5 import QtWidgets, uic, QtCore
import time
import sys
import os
import re

try:
    from sagnacMultitool.aparatus.drivers.ANC300 import ANC300
except ImportError:
    print("Could not import ANC300 module")
    quit()

class MyApp(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        # uic.loadUi("c:/Users/05kyl/Downloads/SagnacOperatingSys/SagnacOperatingSys/MinimalSagnac/Drivers for cryostat.ui", self)
        uic.loadUi("D:/Github/SagnacOperatingSys/MinimalSagnac/Drivers for cryostat.ui", self)

        #used for ANC300 conenction for amp and frequency
        self.stepper = ANC300()
        self.stepper.connect()

        # Connect press/release signals
        # movement btns
        self.btn_up.pressed.connect(lambda:self.move_y(1))
        self.btn_down.pressed.connect(lambda:self.move_y(-1))
        self.btn_left.pressed.connect(lambda:self.move_x(1))
        self.btn_right.pressed.connect(lambda:self.move_x(-1))
        self.btn_up_z.pressed.connect(lambda:self.move_z(1))
        self.btn_down_z.pressed.connect(lambda:self.move_z(-1))

        # ampliitude and volatage btns
        # sets values to whatever the curr val of ANC
        self.btn_Frequency_x.setValue(self.stepper.get_f(6)) #x=6
        self.btn_Frequency_y.setValue(self.stepper.get_f(5)) #y=5
        self.btn_Frequency_z.setValue(self.stepper.get_f(4)) #z=4

        self.btn_Amplitude_x.setValue(self.stepper.get_v(6)) #x=6
        self.btn_Amplitude_y.setValue(self.stepper.get_v(5)) #y=5
        self.btn_Amplitude_z.setValue(self.stepper.get_v(4)) #z=4
        
        # anytime a value is changed for freq or amp it updates
        self.btn_Frequency_x.valueChanged.connect(lambda val: self.update_frequency(6, val)) #x=6
        self.btn_Frequency_y.valueChanged.connect(lambda val: self.update_frequency(5, val)) #y=5
        self.btn_Frequency_z.valueChanged.connect(lambda val: self.update_frequency(4, val)) #z=4

        self.btn_Amplitude_x.valueChanged.connect(lambda val: self.update_amplitude(6, val)) #x=6
        self.btn_Amplitude_y.valueChanged.connect(lambda val: self.update_amplitude(5, val)) #y=5
        self.btn_Amplitude_z.valueChanged.connect(lambda val: self.update_amplitude(4, val)) #z=4


        # capacitance btns
        self.btn_Cap_check.pressed.connect(self.capacitance)

        #ground/unground btns
        self.btn_unground.pressed.connect(self.unground)
        self.btn_ground.pressed.connect(self.ground)

        #continous btns

        self.pressed_keys = set()

        self.move_timer = QtCore.QTimer()
        self.move_timer.timeout.connect(self.handle_movement)
        self.move_timer.start(100)  # check every 100ms

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFocus()




    def keyPressEvent(self, event):
        if self.continous_check.isChecked():
            self.pressed_keys.add(event.key())

    def keyReleaseEvent(self, event):
        self.pressed_keys.discard(event.key())

    def handle_movement(self):
        if not self.continous_check.isChecked():
            return
        
        #fast/slow btns
        if self.radioBtn_fast.isChecked(): #the illusion of choice
            step_size = 10
        else:
            step_size = 1

        if QtCore.Qt.Key_W in self.pressed_keys:
            self.stepper.stepy(step_size)    # Move +Y

        if QtCore.Qt.Key_S in self.pressed_keys:
            self.stepper.stepy(-step_size)   # Move -Y

        if QtCore.Qt.Key_A in self.pressed_keys:
            self.stepper.stepx(-step_size)   # Move -X

        if QtCore.Qt.Key_D in self.pressed_keys:
            self.stepper.stepx(step_size)    # Move +X
        
        if QtCore.Qt.Key_Z in self.pressed_keys:
            self.stepper.stepz(step_size)  # Move Z

        if QtCore.Qt.Key_X in self.pressed_keys:
            self.stepper.stepz(-step_size)   # Move -Z

        


    #the move functions contain both pos and neg depending on the direction
    def move_z(self, direction):
        steps = int(self.btn_Steps_z.value()) #sets the steps to the value of the button
        for _ in range(steps):
            # print(steps) #test
            # print(direction) #test
            print(self.stepper.get_v(4))   # 4 corresponds to z-axis
            print(self.stepper.get_f(4))   # test
            self.stepper.stepz(direction)
            time.sleep(.025) #25ms
            label = "z+" if direction > 0 else "z-"
            print ("stepping in " + label)
        print("done")

    def move_x(self, direction):
        steps = int(self.btn_Steps_x.value())
        for _ in range(steps):
            # print(steps) #test
            # print(direction) #test
            print(self.stepper.get_v(6))   # 6 corresponds to x-axis
            print(self.stepper.get_f(6))   # test
            self.stepper.stepx(direction)
            time.sleep(.025)
            label = "x-" if direction < 0 else "x+"
            print ("stepping in " + label)
        print("done")
    def move_y(self, direction):
        steps = int(self.btn_Steps_y.value())
        for _ in range(steps):
            # print(steps) #test
            # print(direction) #test
            print(self.stepper.get_v(5))   # 5 corresponds to y-axis
            print(self.stepper.get_f(5))   # test     
            self.stepper.stepy(direction)
            time.sleep(.025)
            label = "y+" if direction > 0 else "y-"
            print ("stepping in " + label)
        print("done")


    #updates amplitude respective to axis: x, y, z, and new value
    #go to ANC300 for code
    def update_amplitude(self, axis, value):
        self.stepper.set_amplitude(axis, value)



    #updates frequency respective to axis: x, y, z, and new value
    #go to ANC300 for code
    def update_frequency(self, axis, value):
        self.stepper.set_frequency(axis, value)



    def capacitance(self):
        # make sure its grounded
        
        self.stepper.ground() #maybe needed probably not just to be safe
        # print("FML should go into cap")
        self.stepper.capacitance() #gets the capacitance values
        # print("GOD I LOVE CODING should go to get")
        cap_values = []
        for axis in [6, 5, 4]:
            print(self.stepper.get_capacitance(axis)) #returns capacitance values
            raw = self.stepper.get_capacitance(axis)
            cap = self.parse_capacitance(raw)
            cap_values.append(cap)
        cap_text = "\n".join(str(val) for val in cap_values)
        self.capacitance_text.setText(cap_text)
        # print("FFS should be done")


    

    def ground(self):
        self.stepper.ground() #ground all axis
        print("grounded")

    def unground(self):
        cap_values = []
        for axis in [6, 5, 4]:
            raw = self.stepper.get_capacitance(axis)
            cap = self.parse_capacitance(raw)
            cap_values.append(cap)
        if all(cap > 150 and cap < 1200 for cap in cap_values):
            self.stepper.unground() #unground all axis
            print("ungrounded")
        else:
            print("capactiance value too low")

    #this functions gets the values of the capacitance and put it into an array BC I LOVE CODING
    def parse_capacitance(self, raw):
        match = re.search(r'capacitance\s*=\s*([0-9.]+)', raw)
        
        return float(match.group(1))
        # return raw #test

    def closeEvent(self, event):
        # Automatically ground all axes when the window is closing
        self.stepper.ground()
        print("Axes grounded before closing.")
        event.accept()




if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())
