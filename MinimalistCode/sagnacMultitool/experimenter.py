# from sagnacMachine import set_parameter, perform_measurement
import numpy as np
import sys
import pandas as pd
from itertools import product

## helper functions ##
def hysteresis(npArray):
    return np.concatenate([npArray, npArray[::-1]])

def load_variables_from_csv(csv_file):
    """Loads parameters and headers from the CSV file."""
    # Run CSV code
    with open(csv_file, 'r') as file: # Extract comment by removing the leading '#' and whitespace
        comment_lines = [line.lstrip('#').strip() for line in file if line.startswith('#')]
    python_code = "\n".join(comment_lines) # Combine comments into a single block of Python code
    namespace = {'np': np,'pd':pd, "hysteresis":hysteresis}  # Modules for the `exec` namespace
    exec(python_code, namespace)  # Execute the combined string in namespace

    # Load headers using Pandas
    df = pd.read_csv(csv_file, comment='#')  # Skip Python comments
    headers = list(df.columns)

    return namespace['parameters'], headers, namespace

def set_parameter(non_list_variables, namespace):
    """Set parameters dynamically, supporting method calls and attribute assignment."""
    for name, value in non_list_variables.items():
        print(f"Setting {name} to {value}")
        obj = eval(name, namespace) # Get object from namespace
        if callable(obj):  # call if callable
            obj(value)
        else:  # assign if not callable (for atributtes)
            exec(f"{name} = {value}", namespace)

def perform_measurement(headers, csv_file, namespace):
    """Performs the measurement by evaluating the headers."""
    data = {}
    for header in headers:
        # Evaluate the header (e.g., "inst.attribute")
        obj = eval(header.strip(), namespace)
        data[header] = obj() if callable(obj) else obj

    # Append the data to the CSV file
    df = pd.DataFrame([data], columns=headers)
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

def run_experiment(variables, header, csv_file, namespace):
    # Step 1
    # set top level params, and remove them from the variables dict
    variables = setNpop_topLevel(variables,namespace)
    # Step 2
    if not variables:
        # if there are no variables left, perform the measurement
        perform_measurement(header, csv_file, namespace)
        return
    else:
        print("There are still variables left to set.")
        # take the caresian product of the remaining variables
        prods = cartesian_product(variables)
        # iterate over the products, recursively setting the parameters and performing the measurement
        for prod in prods:
            run_experiment(prod, header, csv_file, namespace)


if __name__ == "__main__":
    # Get the CSV file path from the first command-line argument
    csv_file = sys.argv[1]
    
    # Load and process the CSV file
    parameters, header, namespace = load_variables_from_csv(csv_file)
    run_experiment(parameters, header, csv_file, namespace)
