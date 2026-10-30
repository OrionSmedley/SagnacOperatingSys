# Sample python work around provided by Ren Sci

# import json, socket

# def sendRPC(client, rpc):
#     rpc_bytes = json.dumps(rpc).encode('utf-8')
#     try:
#         client.send(rpc_bytes)
#         response = client.recv(128)
        
#     except socket.error:
#         print("Failed to send data")
        
#     response_json = json.loads(response)
    
#     return response_json

# def main(): # Create a new TCP Soclet connection.
#     try:
#         client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     except socket.error:
#         print("Failed to create socket")
#         sys.exit()
        
#     print("Socket Created")
    
#     IP = "192.168.68.118"
#     PORT = 6002
    
#     client.connect((IP,PORT))
    
#     print("Socket Connected to " + IP)
    
#     rpc = {
#         "method": "goStepsForward",
#         "params":{"1","100","300","1500"},
#         "jsonrpc":"2.0",
#         "id":0,
#     }
#     resp = sendRPC(client, rpc)
#     print("Return Value:" + str(resp["result"]))
    
# if __name__ == "__main__":
#     main()

import json
import socket
import itertools
import time

class RenSciStepper:
    
    def __init__(self, host = "169.254.62.189", port=6002, default_amplitude = 100, default_frequency = 1000, timeout = 3):
        
        # DO NOT EXCEED FOLLOWING VALUES
        # maximum step ampltidude is 300V
        # maximum drive frequency is 4000 Hz
        
        self.host = host
        self.port = port
        self.timeout = timeout 
        
        self.axis_channels = {"x": 1,"y": 2,"z": 3,}

        self._voltage = {"x": 100,"y": 100,"z": 100,}

        self._frequency = {"x": 1000,"y": 1000,"z": 1000,}

        self.positions = {"x": 0.0,"y": 0.0,"z": 0.0,}
        
        self.default_frequency = default_frequency if default_frequency in range(100,4000) else 1000
        self.default_amplitude = default_amplitude if default_amplitude in range(10,300) else 100
        
        self.motion = ["goStepsForward","goStepsReverse","goContinuousForward","goContinuousReverse","goPosition","goInterval"]
        self.movers = {"Single shot": {"forward": "goStepsForward","reverse": "goStepsReverse",},"Burst": {"forward": "goContinuousForward","reverse": "goContinuousReverse",},"Auto": {"autospot": "goPosition", "autowindow":"goInterval",},}
        
        self._id_counter = itertools.count(1)
        
    def connect(self):
        self.sock = socket.create_connection((self.host, self.port),timeout=self.timeout,)
        return self

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
            
    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def _require_connection(self):
        if self.sock is None: raise RuntimeError("Not connected. Call connect() first.")
    
    def call(self, method, params = []):
        """
        Send a generic JSON-RPC method call.
        """
        self._require_connection()

        rpc_id = next(self._id_counter)

        rpc = {"jsonrpc": "2.0","method": method,"params": params,"id": rpc_id,}
        
        if method in self.motion:
            overload = self.call(method="getStatusDriveOverload")
            if overload == False:
                busy = self.call(method="getStatusDriveBusy")
                if busy == True:
                    print("Please let the current process finish")
                    while busy == True:
                        time.sleep(0.01)
                        busy = self.call(method="getStatusDriveBusy")
            else:
                raise ValueError("Please adjust the voltage or frequency of the steppers")
            
        request = json.dumps(rpc).encode("utf-8")
        self.sock.sendall(request)

        response = self._receive_json_response()
        # print("Response is:")
        # print(response)
        # print(type(response.get("result")))

        if response.get("id") != str(rpc_id):
            raise RuntimeError(f"Response ID mismatch. Sent id={rpc_id}, "f"received id={response.get('id')}")

        if "error" in response:
            raise RuntimeError(f"JSON-RPC error: {response['error']}")

        return response.get("result")
    
    def _receive_json_response(self):
        buffer = bytearray()
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Socket closed before response was received.")
            buffer.extend(chunk)
            try:
                text = buffer.decode("utf-8")
                return json.loads(text)
            except json.JSONDecodeError:
                # Response may be incomplete; keep reading.
                continue
    
    #### Properties
    
    def set_channel(self, channel):
        self.channel = self.channel_control(channel)
        
    def get_channel(self):
        return self.call(method="getDriveChannel")
    
    def get_channel_for_axis(self, axis):
        axis = axis.lower()
        return self.axis_channels[axis]
    
    channel = property(get_channel,set_channel)
    channel_dict = {1:"x",2:"y",3:"z"}   
    
    def channel_control(self, channel):
        response = self.call(method="getDriveChannel")
        set_to = int(channel)
        while set_to != response:
            check = self.call(method="setDriveChannel",params=[channel])
            response = self.call(method="getDriveChannel")
            if check == True and set_to == response:
                break
        print(f"Set stepper control to {self.channel_dict[set_to]}")
        return set_to
    
    def get_frequency(self, axis):
        axis = axis.lower()

        if axis not in self._frequency:
            raise ValueError(f"Unknown axis {axis!r}")

        return self._frequency[axis]

    def set_frequency(self, axis, value):
        axis = axis.lower()

        if axis not in self._frequency:
            raise ValueError(f"Unknown axis {axis!r}")

        value = int(value)

        if not 100 <= value <= 4000:
            raise ValueError("frequency must be within [100, 4000] Hz")

        self._frequency[axis] = value

    @property
    def frequency_x(self):
        return self.get_frequency("x")

    @frequency_x.setter
    def frequency_x(self, value):
        self.set_frequency("x", value)

    @property
    def frequency_y(self):
        return self.get_frequency("y")

    @frequency_y.setter
    def frequency_y(self, value):
        self.set_frequency("y", value)

    @property
    def frequency_z(self):
        return self.get_frequency("z")

    @frequency_z.setter
    def frequency_z(self, value):
        self.set_frequency("z", value)
    

    def get_voltage(self, axis):
        axis = axis.lower()

        if axis not in self._voltage:
            raise ValueError(f"Unknown axis {axis!r}")

        return self._voltage[axis]

    def set_voltage(self, axis, value):
        axis = axis.lower()

        if axis not in self._voltage:
            raise ValueError(f"Unknown axis {axis!r}")

        value = int(value)

        if not 10 <= value <= 300:
            raise ValueError("Voltage must be within [10, 300] V")

        self._voltage[axis] = value

    @property
    def voltage_x(self):
        return self.get_voltage("x")

    @voltage_x.setter
    def voltage_x(self, value):
        self.set_voltage("x", value)

    @property
    def voltage_y(self):
        return self.get_voltage("y")

    @voltage_y.setter
    def voltage_y(self, value):
        self.set_voltage("y", value)

    @property
    def voltage_z(self):
        return self.get_voltage("z")

    @voltage_z.setter
    def voltage_z(self, value):
        self.set_voltage("z", value)
        
    ### Manual motion
    
    def set_move_method(self, direction, mode):
        if mode != "Auto":
            direction = "forward" if direction >= 0 else "reverse"
            print(f"Set method to {self.movers[mode][direction]}")
            return self.movers[mode][direction]
        else:
            raise ValueError("Please input one of the valid modes: ['Single shot', 'Burst']")
        
    def get_axis_settings(self, axis):
        axis = axis.lower()

        return {
            "channel": self.get_channel_for_axis(axis),
            "voltage": self.get_voltage(axis),
            "frequency": self.get_frequency(axis),
        }
        
    def step_axis(self, axis, step_size, mode="Single shot"):
        axis = axis.lower()

        method = self.set_move_method(direction=step_size, mode=mode)

        channel = self.axis_channels[axis]
        voltage = self._voltage[axis]
        frequency = self._frequency[axis]
        
        print(f"Stepping channel {channel} @ {voltage}V and {frequency}Hz")

        response = self.call(
            method=method,
            params=[
                channel,
                abs(int(step_size)),
                voltage,
                frequency,
            ],
        )

        if response is True:
            sign = "+" if step_size > 0 else "-"
            print(f"Stepped in {sign}{axis}")

        return response

    def step_x(self, step_size, mode="Single shot"):
        return self.step_axis("x", step_size, mode=mode)


    def step_y(self, step_size, mode="Single shot"):
        return self.step_axis("y", step_size, mode=mode)


    def step_z(self, step_size, mode="Single shot"):
        return self.step_axis("z", step_size, mode=mode)
            
    def continuous_axis(self, axis, step_size, mode="Burst"):
        method = self.set_move_method(direction=step_size, mode=mode)

        settings = self.get_axis_settings(axis)

        return self.call(
            method=method,
            params=[
                settings["channel"],
                settings["voltage"],
                settings["frequency"],
            ],
        )
        
    def continuous_x(self, step_size, mode="Burst"):
        return self.continuous_axis("x", step_size, mode=mode)


    def continuous_y(self, step_size, mode="Burst"):
        return self.continuous_axis("y", step_size, mode=mode)


    def continuous_z(self, step_size, mode="Burst"):
        return self.continuous_axis("z", step_size, mode=mode)
        
    #### Automated motion (needs position encoders)
        
    target_positions = {"x":0,"y":0,"z":0}     
        
    def get_positions(self):
        for axis, channel in self.axis_channels.items():
            position_meters = self.call(
                method="getPosition",
                params=[channel],
            )

            self.positions[axis] = round(position_meters * 1e6, 9)

        return self.positions
        
    def go_to_positions(self, target_positions):

        for axis, channel in self.axis_channels.items():
            target_um = target_positions[axis]
            voltage = self._voltage[axis]
            frequency = self._frequency[axis]
            print(f"Moving {axis}")
            response = self.call(
                method="goPosition",
                params=[
                    channel,
                    target_um *1e-6,
                    voltage,
                    frequency,
                ],
            )
            while abs(round(self.call(method="getPosition", params=[channel]) *1e6,9)-target_um) > 0.02:
                time.sleep(0.05)
                if abs(self.positions[axis]-target_um) <= 0.02:
                    print("There")
                    break
            busy = True
            while busy:
                print("Busy")
                busy = self.call("getStatusDriveBusy")
                time.sleep(0.01)

        return True
        
    def stop(self):
        self.call(method="stopMotion")
        
    def ground(self):
        self.call(method="setDriveChannelsOff")   