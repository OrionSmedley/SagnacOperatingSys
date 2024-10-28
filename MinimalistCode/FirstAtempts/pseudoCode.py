def set_parameter(name, value):
    """Simulate setting a parameter on the apparatus."""
    print(f"Setting {name} to {value}")

def perform_measurement(current_state):
    """Simulate performing a measurement with the current apparatus settings."""
    print("Performing measurement")
    # Simulate data collection
    data = {"measurement_result": 42}  # Placeholder for actual data
    # Combine current_state and data for recording
    record = {**current_state, **data}
    print(f"Recorded data: {record}")

def run_experiment(variables):
    # Step 1
    # set top level params, and remove them from the variables dict
    variables = setPop_TLP(variables)
    # Step 2
    if not variables:
        # if there are no variables left, perform the measurement
        perform_measurement()
        return
    else:
        # take the caresian product of the remaining variables
        products = cartesian_product(variables)
        # iterate over the products, recursively setting the parameters and performing the measurement
        for product in products:
            run_experiment(product)


# User-provided variables
variables = {
    'T': 45,
    'B': [-100, 100],
    'B_sweep': [[0, 1, 2], [0, -1, -2]],
    'V': [[-1, 1]]
}

run_experiment(variables)