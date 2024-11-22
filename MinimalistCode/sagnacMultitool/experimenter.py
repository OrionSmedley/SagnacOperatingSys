# from sagnacMachine import set_parameter, perform_measurement
import numpy as np

def setNpop_topLevel(variables):
    non_list_variables = {k: v for k, v in variables.items() if not isinstance(v, (list, np.ndarray))}
    set_parameter(**non_list_variables)
    remaining_variables = {k: v for k, v in variables.items() if isinstance(v, (list, np.ndarray))}
    return remaining_variables


from itertools import product

def cartesian_product(dicts):
    return (dict(zip(dicts, x)) for x in product(*dicts.values()))


def run_experiment(variables, savePath):
    # Step 1
    # set top level params, and remove them from the variables dict
    variables = setNpop_topLevel(variables)
    # Step 2
    if not variables:
        # if there are no variables left, perform the measurement
        perform_measurement(savePath)
        return
    else:
        print("There are still variables left to set.")
        # take the caresian product of the remaining variables
        prods = cartesian_product(variables)
        # iterate over the products, recursively setting the parameters and performing the measurement
        for prod in prods:
            run_experiment(prod, savePath)


# User-provided variables

def hysteresis(npArray):
    return np.concatenate([npArray, npArray[::-1]])

import numpy as np
import sys
import pandas as pd



def load_variables_from_csv(csv_file):
    """Loads parameters and headers from the CSV file."""
    with open(csv_file, 'r') as file:
        # Extract comment lines and remove the leading '#' and any whitespace
        comment_lines = [line.lstrip('#').strip() for line in file if line.startswith('#')]
    
    # Combine all comment lines into a single block of Python code
    python_code = "\n".join(comment_lines)
    print("Executing CSV code: \n\t", python_code)

    namespace = {'np': np}  # Modules for the `exec` namespace
    exec(python_code, namespace)  # Execute the combined string in namespace

    # Load headers using Pandas
    try:
        df = pd.read_csv(csv_file, comment='#')  # Skip Python comments
        headers = list(df.columns)
    except pd.errors.EmptyDataError:
        headers = []  # No data yet, assume headers not defined

    parameters = namespace.get('parameters', {})
    return parameters, headers, namespace









if __name__ == "__main__":
    # Get the CSV file path from the first command-line argument
    csv_file = sys.argv[1]
    
    # Load and process the CSV file
    parameters = load_variables_from_csv(csv_file)
    run_experiment(parameters, csv_file)


