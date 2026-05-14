import pyvisa
import time
import numpy as np
    
class Lakeshore336:
    
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource("TCPIP0::169.254.62.185::7777::SOCKET")
        self.instrument.read_termination = '\r\n'
        self.instrument.write_termination = '\r\n'
        self.PID_table = {0: "PID 1, 300, 60, 0.1", 1: "PID 1, 300, 60, 0.1", 2: "PID 1, 300, 30, 0", 3: "PID 1, 50, 3, 5"}
        self.levels = {0: "off", 1: "low", 2: "medium", 3: "high"}
        self.PID = None

    def query(self, command):
        return self.instrument.query(command)

    def write(self, command):
        self.instrument.write(command)

    def get_sample_temp(self):
        """Calls LK336 to read all temperatures. Parses down to channels A and B"""
        response = self.query(f'KRDG? a')
        return float(response.strip())

    def get_vti_temp(self):
        """Calls LK336 to read all temperatures. Parses down to channels A and B"""
        response = self.instrument.query(f'KRDG? b')
        return float(response.strip())
    
    def sample_heater_toggle(self, range):
        toggle = int(self.query("RANGE? 1"))
        self.PID = self.PID_table.get(int(range), "unknown")
        self.instrument.write(self.PID)
        if toggle != range:
            while toggle != range:
                self.instrument.write(f"RANGE 1, {range}")
                toggle = self.instrument.query("RANGE? 1")
                toggle = int(toggle.strip())
        print(f"Sample Heater Range set to {toggle} with {self.PID}")
        
    def monitor_temps(self, setpoint, trials = 1500):
        res = self.query("SETP? 1")
        setp = float(res.replace('+', ''))
        temp, temp_avg, variance = [], 0, 0
        time_0 = time.time()

        for _ in range(trials):
            temp.append(self.get_sample_temp())
        temp_avg = np.mean(temp)
        temp_diff = temp[-1] - temp[0] 

        for i in range(len(temp)):
            variance += (temp[i] - temp_avg)**2

        variance = np.sqrt(variance/trials)
        htr_power = float(self.query("HTR? 1").replace('+',''))
        mode = self.levels.get(int(self.query('RANGE? 1').strip()), "unknown")
        time_1 = time.time() - time_0 
        heating_speed = round(temp_diff/time_1,5)
        if heating_speed != 0:
            time_remaining = round(abs((setp-self.get_sample_temp())/heating_speed))
        else:
            time_remaining = 0

        if setpoint != setp:
            print(f"Set point is {setp} K")
        print(f"Current temp is {round(temp_avg,3)}({round(variance,3)}) K at {htr_power}% power (mode: {mode})")
        if time_remaining%60 < 10:
            print(f"Temperature is changing at {round(heating_speed*1000)} mK/s (remaining: {time_remaining//60}:0{time_remaining%60})")
        else: 
            print(f"Temperature is changing at {round(heating_speed*1000)} mK/s (remaining: {time_remaining//60}:{time_remaining%60})")
        
        if abs(heating_speed*1000) > 2 or abs(setp-self.get_sample_temp()) > 0.005 or variance > 0.015:
            return False
        else:
            return True
        
    def set_sample_temp(self, temperature):
        status = False
        temp = np.round(self.get_sample_temp(),2)
        setpoint = self.instrument.query(f"SETP? 1")
        setpoint = float(setpoint.strip())

        if temperature > 320:
            return print(f"Setpoint too high. Please set the temp to 320 K or less.")

        elif setpoint == float(temperature) and temperature == temp:
            print(f"Sample Heater already set to {temperature}")
            
        elif temperature <= 8: # uses low power mode to heat sample between 1.7 - 8 K
            self.sample_heater_toggle(1)
            setpoint = self.instrument.query(f"SETP? 1")
            setpoint = float(setpoint.strip())
            temp = np.round(self.get_sample_temp(),2)
            if temperature != temp:
                if setpoint != float(temperature):
                    self.instrument.write(f"SETP 1, {temperature}")
                    print(f"Sample Heater setpoint going to final setpoint {temperature} K")
                
                temp = self.get_sample_temp()
                if temp != temperature:
                    while status == False:
                        status = self.monitor_temps(temperature)
                            
        elif (temperature > 8 and temperature <= 45) or temperature > 220 or temp > 220: # uses medium power mode to heat sample between 8 - 45 K
            self.sample_heater_toggle(2)
            setpoint = self.instrument.query(f"SETP? 1")
            setpoint = float(setpoint.strip())
            temp = np.round(self.get_sample_temp(),2)
            if temperature != temp:
                if setpoint != float(temperature):
                    self.instrument.write(f"SETP 1, {temperature}")
                    print(f"Sample Heater setpoint going to final setpoint {temperature} K")
                
                temp = self.get_sample_temp()
                if temp != temperature:
                    while status == False:
                        status = self.monitor_temps(temperature)
        
        elif temperature > 45 and temperature <=220: # uses high power mode to heat sample between 45 and n.a. K
            # self.sample_heater_toggle(2)
            
            setpoint = self.instrument.query(f"SETP? 1")
            setpoint = float(setpoint.strip())
            temp = np.round(self.get_sample_temp(),2)
            if setpoint != float(temperature):
                self.instrument.write(f"SETP 1, {temperature}")
                print(f"Sample Heater setpoint going to final setpoint {temperature} K")
              
            if temp > 220:
                self.sample_heater_toggle(2)
                while temp > 220:
                    temp = self.get_sample_temp()
                    status = self.monitor_temps(temperature)
            elif temp < 220:
                self.sample_heater_toggle(3)
                if temperature != temp:
                    temp = self.get_sample_temp()
                    if temp != temperature:
                        while status == False:
                            status = self.monitor_temps(temperature)


                    
    def set_vti_temp(self, temperature):
        temp = self.get_vti_temp()
        if temperature > 320:
            return print(f"Setpoint too high. Please set the temp to 320 K or less.")
        # elif temp > 320 or temperature > 300: 
        #     temp = self.get_vti_temp()
        #     self.instrument.write(f"SETP 2, {temperature}")
        #     setpoint = self.instrument.query(f"SETP? 2")
        #     setpoint = float(setpoint.strip())
        #     print(f"VTI Heater Limit Set to {setpoint} K")
        #     temp = np.round(self.get_sample_temp(),2)
        #     while temp != setpoint:
        #         if temp > temperature:
        #             if (temp -  temperature) > 1:
        #                 toggle = self.instrument.query("RANGE? 2")
        #                 if toggle == '0':
        #                     time.sleep(5)
        #                     temp = np.round(self.get_vti_temp(),2)
        #                     print(f"Waiting for VTI to cool from {temp}K to {setpoint}K")
        #                 elif toggle != '0':
        #                     self.instrument.write(f"RANGE 2, 0")
        #                     toggle = self.instrument.query("RANGE? 2")
        #                     toggle = int(toggle.strip())
        #                     print(f"VTI Heater Range set to {toggle}")
        #                     time.sleep(5)
        #                     temp = np.round(self.get_vti_temp(),2)
        #                     print(f"Waiting for VTI to cool from {temp}K to {setpoint}K")
        #         if temp < temperature + 1 :
        #             toggle = self.instrument.query("RANGE? 2")
        #             if toggle != '1':
        #                 self.instrument.write(f"RANGE 2, 1")
        #                 toggle = self.instrument.query("RANGE? 2")
        #                 toggle = int(toggle.strip())
        #                 print(f"VTI Heater Range set to {toggle}")
        #             time.sleep(5)
        #             temp = np.round(self.get_vti_temp(),2)
        #             print(f"Waiting for VTI to go from {temp}K to {setpoint}K")
        else:
            setpoint = self.instrument.query(f"SETP? 2")
            setpoint = float(setpoint.strip())
            temp = np.round(self.get_vti_temp(),2)
            if temperature != temp:
                if setpoint != float(temperature):
                    while setpoint != float(temperature):
                        self.instrument.write(f"SETP 2, {temperature}")
                        setpoint = self.instrument.query(f"SETP? 2")
                        setpoint = float(setpoint.strip())
                    print(f"VTI Heater Limit Set to {setpoint} K")
                    
                    temp = self.get_vti_temp()
                    while temp != setpoint:
                        if temp > temperature:
                            if (temp -  temperature) >= 10:
                                toggle = self.instrument.query("RANGE? 2")
                                if toggle == '0':
                                    time.sleep(5)
                                    temp = np.round(self.get_vti_temp(),2)
                                elif toggle != '0':
                                    self.instrument.write(f"RANGE 2, 0")
                                    toggle = self.instrument.query("RANGE? 2")
                                    toggle = int(toggle.strip())
                                    print(f"VTI Heater Range set to {toggle}")
                                    time.sleep(5)
                                    temp = np.round(self.get_vti_temp(),2)
                                print(f"Waiting for VTI to cool from {temp}K to {setpoint}K")
                        if temp < temperature + 10 :
                            toggle = self.instrument.query("RANGE? 2")
                            if toggle != '3':
                                self.instrument.write(f"RANGE 2, 3")
                                toggle = self.instrument.query("RANGE? 2")
                                toggle = int(toggle.strip())
                                print(f"VTI Heater Range set to {toggle}")
                            time.sleep(5)
                            temp = np.round(self.get_vti_temp(),2)
                            print(f"Waiting for VTI to go from {temp}K to {setpoint}K")
                else:
                    temp = self.get_vti_temp()
                    while temp != setpoint:
                        if temp > temperature:
                            if (temp -  temperature) >= 10:
                                toggle = self.instrument.query("RANGE? 2")
                                if toggle == '0':
                                    time.sleep(5)
                                    temp = np.round(self.get_vti_temp(),2)
                                elif toggle != '0':
                                    self.instrument.write(f"RANGE 2, 0")
                                    toggle = self.instrument.query("RANGE? 2")
                                    toggle = int(toggle.strip())
                                    print(f"VTI Heater Range set to {toggle}")
                                    time.sleep(5)
                                    temp = np.round(self.get_vti_temp(),2)
                                print(f"Waiting for VTI to cool from {temp}K to {setpoint}K")
                        if temp < temperature + 10 :
                            toggle = self.instrument.query("RANGE? 2")
                            if toggle != '3':
                                self.instrument.write(f"RANGE 2, 3")
                                toggle = self.instrument.query("RANGE? 2")
                                toggle = int(toggle.strip())
                                print(f"VTI Heater Range set to {toggle}")
                            time.sleep(5)
                            temp = np.round(self.get_vti_temp(),2)
                            print(f"Waiting for VTI to go from {temp}K to {setpoint}K")       
            elif setpoint == float(temperature) and temperature == temp:
                print(f"VTI Heater already set to {temperature}")
                
    def set_hermes_temps(self, temperature):
        samptemp = self.get_sample_temp()
        vtitemp = self.get_vti_temp()
        if temperature > 320:
            return print(f"Setpoint too high. Please set the temp to 320 K or less.")
        else:
            sampsetpoint = self.instrument.query(f"SETP? 1")
            sampsetpoint = float(sampsetpoint.strip())
            samptemp = np.round(self.get_sample_temp(),2)
            
            vtisetpoint = self.instrument.query(f"SETP? 2")
            vtisetpoint = float(vtisetpoint.strip())
            vtitemp = np.round(self.get_vti_temp(),2)
            
            if temperature != vtitemp:
                if vtisetpoint != float(temperature):
                    while vtisetpoint != float(temperature):
                        self.instrument.write(f"SETP 2, {temperature}")
                        time.sleep(0.2)
                        vtisetpoint = self.instrument.query(f"SETP? 2")
                        # print(vtisetpoint)
                        vtisetpoint = float(vtisetpoint.strip())
            print(f"VTI Heater Limit Set to {vtisetpoint} K")
            
            if temperature != samptemp:
                if sampsetpoint != float(temperature):
                    while sampsetpoint != float(temperature):
                        self.instrument.write(f"SETP 1, {temperature}")
                        sampsetpoint = self.instrument.query(f"SETP? 1")
                        sampsetpoint = float(sampsetpoint.strip())
            print(f"Sample Heater Limit Set to {sampsetpoint} K")
            samptemp = self.get_sample_temp()
            vtitemp = self.get_vti_temp()
            
            if vtitemp >= vtisetpoint and samptemp >= sampsetpoint:
                while vtitemp >= vtisetpoint or samptemp >= sampsetpoint:
                    if vtitemp != vtisetpoint:
                        if vtitemp > temperature:
                            if (vtitemp -  temperature) >= 10:
                                toggle = self.instrument.query("RANGE? 2")
                                if toggle == '0':
                                    time.sleep(5)
                                    vtitemp = np.round(self.get_vti_temp(),2)
                                elif toggle != '0':
                                    self.instrument.write(f"RANGE 2, 0")
                                    toggle = self.instrument.query("RANGE? 2")
                                    toggle = int(toggle.strip())
                                    print(f"VTI Heater Range set to {toggle}")
                                    time.sleep(5)
                                    vtitemp = np.round(self.get_vti_temp(),2)
                                print(f"Waiting for VTI to cool from {vtitemp}K to {vtisetpoint}K")
                                if vtitemp < temperature + 10 :
                                    toggle = self.instrument.query("RANGE? 2")
                                    if toggle != '3':
                                        self.instrument.write(f"RANGE 2, 3")
                                        toggle = self.instrument.query("RANGE? 2")
                                        toggle = int(toggle.strip())
                                        print(f"VTI Heater Range set to {toggle}")
                                    time.sleep(5)
                                    vtitemp = np.round(self.get_vti_temp(),2)
                                    print(f"Waiting for VTI to go from {vtitemp}K to {vtisetpoint}K")
                    if samptemp != sampsetpoint:
                        if samptemp > temperature:
                                if (samptemp -  temperature) > 10:
                                    toggle = self.instrument.query("RANGE? 1")
                                    if toggle == '0':
                                        time.sleep(5)
                                        samptemp = np.round(self.get_sample_temp(),2)
                                    elif toggle != '0':
                                        self.instrument.write(f"RANGE 1, 0")
                                        toggle = self.instrument.query("RANGE? 1")
                                        toggle = int(toggle.strip())
                                        print(f"Sample Heater Range set to {toggle}")
                                        time.sleep(5)
                                        samptemp = np.round(self.get_sample_temp(),2)
                                    print(f"Waiting for Sample to cool from {samptemp}K to {sampsetpoint}K")
                                if samptemp < temperature + 10 :
                                        toggle = self.instrument.query("RANGE? 1")
                                        if toggle != '2':
                                            self.instrument.write(f"RANGE 1, 2")
                                            toggle = self.instrument.query("RANGE? 1")
                                            toggle = int(toggle.strip())
                                            print(f"Sample Heater Range set to {toggle}")
                                        time.sleep(5)
                                        samptemp = np.round(self.get_sample_temp(),2)
                                        print(f"Waiting for Sample to go from {samptemp}K to {sampsetpoint}K")
            elif vtitemp < vtisetpoint and samptemp < sampsetpoint:
                while vtitemp < vtisetpoint or samptemp < sampsetpoint:
                    if vtitemp != vtisetpoint:
                        if vtitemp > temperature:
                            if (vtitemp -  temperature) >= 10:
                                toggle = self.instrument.query("RANGE? 2")
                                if toggle == '0':
                                    time.sleep(5)
                                    vtitemp = np.round(self.get_vti_temp(),2)
                                elif toggle != '0':
                                    self.instrument.write(f"RANGE 2, 0")
                                    toggle = self.instrument.query("RANGE? 2")
                                    toggle = int(toggle.strip())
                                    print(f"VTI Heater Range set to {toggle}")
                                    time.sleep(5)
                                    vtitemp = np.round(self.get_vti_temp(),2)
                                print(f"Waiting for VTI to cool from {vtitemp}K to {vtisetpoint}K")
                        if vtitemp < temperature:
                            if vtitemp < temperature + 10 :
                                toggle = self.instrument.query("RANGE? 2")
                                if toggle != '3':
                                    self.instrument.write(f"RANGE 2, 3")
                                    toggle = self.instrument.query("RANGE? 2")
                                    toggle = int(toggle.strip())
                                    print(f"VTI Heater Range set to {toggle}")
                                time.sleep(5)
                                vtitemp = np.round(self.get_vti_temp(),2)
                                print(f"Waiting for VTI to go from {vtitemp}K to {vtisetpoint}K")
                    if samptemp != sampsetpoint:
                        if samptemp > temperature:
                                if (samptemp -  temperature) > 10:
                                    toggle = self.instrument.query("RANGE? 1")
                                    if toggle == '0':
                                        time.sleep(5)
                                        samptemp = np.round(self.get_sample_temp(),2)
                                    elif toggle != '0':
                                        self.instrument.write(f"RANGE 1, 0")
                                        toggle = self.instrument.query("RANGE? 1")
                                        toggle = int(toggle.strip())
                                        print(f"Sample Heater Range set to {toggle}")
                                        time.sleep(5)
                                        samptemp = np.round(self.get_sample_temp(),2)
                                    print(f"Waiting for Sample to cool from {samptemp}K to {sampsetpoint}K")
                        if samptemp < temperature:
                            if samptemp < temperature + 10 :
                                    toggle = self.instrument.query("RANGE? 1")
                                    if toggle != '2':
                                        self.instrument.write(f"RANGE 1, 2")
                                        toggle = self.instrument.query("RANGE? 1")
                                        toggle = int(toggle.strip())
                                        print(f"Sample Heater Range set to {toggle}")
                                    time.sleep(5)
                                    samptemp = np.round(self.get_sample_temp(),2)
                                    print(f"Waiting for Sample to go from {samptemp}K to {sampsetpoint}K")
            else:
                vtitemp = self.get_vti_temp()
                samptemp = self.get_sample_temp()
                if vtitemp != vtisetpoint or samptemp != sampsetpoint:
                    while vtitemp != vtisetpoint or samptemp != sampsetpoint:
                        if vtitemp != vtisetpoint:
                            if vtitemp > temperature:
                                if (vtitemp -  temperature) >= 10:
                                    toggle = self.instrument.query("RANGE? 2")
                                    if toggle == '0':
                                        time.sleep(5)
                                        vtitemp = np.round(self.get_vti_temp(),2)
                                    elif toggle != '0':
                                        self.instrument.write(f"RANGE 2, 0")
                                        toggle = self.instrument.query("RANGE? 2")
                                        toggle = int(toggle.strip())
                                        print(f"VTI Heater Range set to {toggle}")
                                        time.sleep(5)
                                        vtitemp = np.round(self.get_vti_temp(),2)
                                print(f"Waiting for VTI to cool from {vtitemp}K to {vtisetpoint}K")
                            if vtitemp < temperature + 10 :
                                toggle = self.instrument.query("RANGE? 2")
                                if toggle != '3':
                                    self.instrument.write(f"RANGE 2, 3")
                                    toggle = self.instrument.query("RANGE? 2")
                                    toggle = int(toggle.strip())
                                    print(f"VTI Heater Range set to {toggle}")
                                time.sleep(5)
                                vtitemp = np.round(self.get_vti_temp(),2)
                                print(f"Waiting for VTI to go from {vtitemp}K to {vtisetpoint}K")
                        if samptemp != sampsetpoint:
                            if samptemp > temperature:
                                if (samptemp -  temperature) > 10:
                                    toggle = self.instrument.query("RANGE? 1")
                                    if toggle == '0':
                                        time.sleep(5)
                                        samptemp = np.round(self.get_sample_temp(),2)
                                    elif toggle != '0':
                                        self.instrument.write(f"RANGE 1, 0")
                                        toggle = self.instrument.query("RANGE? 1")
                                        toggle = int(toggle.strip())
                                        print(f"Sample Heater Range set to {toggle}")
                                        time.sleep(5)
                                        samptemp = np.round(self.get_sample_temp(),2)
                                print(f"Waiting for Sample to cool from {samptemp}K to {sampsetpoint}K")
                            if samptemp < temperature + 10 :
                                toggle = self.instrument.query("RANGE? 1")
                                if toggle != '2':
                                    self.instrument.write(f"RANGE 1, 2")
                                    toggle = self.instrument.query("RANGE? 1")
                                    toggle = int(toggle.strip())
                                    print(f"Sample Heater Range set to {toggle}")
                                time.sleep(5)
                                samptemp = np.round(self.get_sample_temp(),2)
                                print(f"Waiting for Sample to go from {samptemp}K to {sampsetpoint}K")       
                elif vtisetpoint == float(temperature) and temperature == vtitemp and sampsetpoint == float(temperature) and temperature == samptemp:
                    print(f"VTI Heater already set to {temperature}")
                    print(f"Sample Heater already set to {temperature}")

               

                           

        