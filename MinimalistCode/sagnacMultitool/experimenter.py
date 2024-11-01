from sagnacMachine import set_parameter, perform_measurement
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
tc = 0.01
variables = {
    'Tc': [tc],
    'B': [np.linspace(-0.1, 0.1, 20+1)],
    'wait': [[10*tc]]
}
savePath = 'data.csv'


run_experiment(variables, savePath)


