import numpy as np
import sys
import pandas as pd
from itertools import product

def print_nicely(obj, n=3):
    """Prints a nested object nicely. Written By GPT"""
    import pprint, builtins
    if isinstance(obj, str): return builtins.print(obj)
    def _p(o):
        if isinstance(o, np.ndarray): return _p(o.tolist())
        if isinstance(o, (list, tuple)):
            o = [_p(x) for x in o]
            return o if len(o) <= 2*n+3 else o[:n] + ['...'] + o[-n:]
        if isinstance(o, dict): return {k: _p(v) for k, v in o.items()}
        return o
    pprint.pp(_p(obj), sort_dicts=False)
# print = print_nicely

def load_variables_from_csv(csv_file, commentChar = ';'):
    """Loads parameters from the CSV file."""
    # Run CSV code
    with open(csv_file, 'r') as file: # Extract comment by removing the leading ';' and whitespace
        comment_lines = [line.lstrip(commentChar) for line in file if line.startswith(commentChar)]   #removed .strip() from line.lstrip(commentChar).strip() to keep the indentation
    python_code = "\n".join(comment_lines) # Combine comments into a single block of Python code
    namespace = {}  # Modules for the `exec` namespace
    exec(python_code, namespace)  # Execute the combined string in namespace

    return namespace['parameters'], namespace

def set_parameter(non_list_variables, namespace):
    """Set parameters dynamically, supporting method calls and attribute assignment."""
    for name, value in non_list_variables.items():
        print(f"\tSetting {name} to {value}")
        name = name.split('#')[0].strip() # Remove comments from the name
        obj = eval(name, namespace) # dummy proof: errors if user doesn't define name
        try: # Try to call the value if it's callable
            exec(f"({name})({value})", namespace)
        except:  # Try to assign the value directly
            exec(f"{name} = {value}", namespace) 

def perform_measurement(csv_file, namespace, commentChar = ';'):
    """Performs the measurement by evaluating the headers."""
    print("\tMeasuring...\n")
    # Load headers using Pandas
    df = pd.read_csv(csv_file, comment=commentChar)  # Skip Python comments
    headers = list(df.columns)
    
    data = {}
    for header in headers:
        # Evaluate the header (e.g., "inst.attribute")
        obj = eval(header.strip(), namespace)
        data[header] = obj() if callable(obj) else obj

    # Append the data to the CSV file
    df = pd.DataFrame(data,index=[0])
    df.to_csv(csv_file, mode='a', header=False, index=False)
    return data

#### Running the experiment

def setNpop_topLevel(variables, namespace):
    non_list_variables = {k: v for k, v in variables.items() if not isinstance(v, (list, np.ndarray))}
    set_parameter(non_list_variables, namespace)
    remaining_variables = {k: v for k, v in variables.items() if isinstance(v, (list, np.ndarray))}
    return remaining_variables

def cartesian_product(dicts): # cartesian product for dictionaries
    return (dict(zip(dicts, x)) for x in product(*dicts.values()))

def run_experiment(variables, csv_file, namespace, demoMode = True):
    print("Running experiment with variables:")
    print_nicely(variables)
    # Step 1: set top level params, and remove them from the variables dict
    variables = setNpop_topLevel(variables,namespace)
    # Step 2
    if not variables:
        # if there are no variables left, perform the measurement
        perform_measurement(csv_file, namespace)
        return
    else:
        print("\nCartesian Product of remaining variables:")
        # take the caresian product of the remaining variables
        prods = cartesian_product(variables)
        # iterate over the products, recursively setting the parameters and performing the measurement
        for prod in prods:
            run_experiment(prod, csv_file, namespace,demoMode)

if __name__ == "__main__":
    # Get the CSV file path from the first command-line argument
    csv_file = sys.argv[1]

    print("_________________________________________________")
    print("Execute CSV's python \n")
    parameters, namespace = load_variables_from_csv(csv_file)

    print("_________________________________________________")
    print("python parameters -->> experiment \n")
    run_experiment(parameters, csv_file, namespace)
    
    print("_________________________________________________")
    print("Wrapping up and going home :) \n")
    # wrapUp(parameters, csv_file, namespace)
    exec("wrapUp()", namespace)

