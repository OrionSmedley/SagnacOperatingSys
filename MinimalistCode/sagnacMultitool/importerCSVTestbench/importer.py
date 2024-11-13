import numpy as np

def example_function():
    global parameters
    exec("parameters = {'B': [5, 7], 'V': np.linspace(0, 10, 11)}")
    # print("globals: ", globals() )
    print("locals: ", locals() )
    print(parameters)  # Raises NameError

example_function()