from itertools import product

def set_parameters(params):
    """Simulate setting multiple parameters on the apparatus."""
    params_str = ', '.join(f"{k}={v}" for k, v in params.items())
    print(f"Setting parameters: {params_str}")

def perform_measurement(current_state):
    """Simulate performing a measurement with the current apparatus settings."""
    print("Performing measurement")
    # Simulate data collection (replace with actual measurement logic)
    data = {"measurement_result": 42}  # Placeholder for actual data
    # Combine current_state and data for recording
    record = {**current_state, **data}
    print(f"Recorded data: {record}")

def run_experiment(variables, current_state=None):
    if current_state is None:
        current_state = {}

    # Step 1: Initialize all non-list variables not yet set
    initial_params = {k: v for k, v in variables.items() if not isinstance(v, list) and k not in current_state}
    if initial_params:
        set_parameters(initial_params)
        current_state.update(initial_params)

    # Step 2: Identify all list variables that need to be unpacked
    variables_to_unpack = {k: v for k, v in variables.items() if isinstance(v, list) and k not in current_state}
    if not variables_to_unpack:
        # All variables are set; perform measurement
        perform_measurement(current_state)
        return

    # Step 3: Unpack all list variables one level
    var_names = list(variables_to_unpack.keys())
    var_values_lists = []
    for var_value in variables_to_unpack.values():
        if isinstance(var_value[0], list):
            # Variable is a list of lists; unpack one level
            var_values_lists.append(var_value)
        else:
            # Variable is a flat list; wrap each value in a list for consistency
            var_values_lists.append([[v] for v in var_value])

    # Step 4: Generate all combinations of the unpacked variables
    for combination in product(*var_values_lists):
        # Prepare parameters to set in this iteration
        params_to_set = {}
        new_variables = variables.copy()
        new_state = current_state.copy()

        for var_name, var_value in zip(var_names, combination):
            if isinstance(var_value, list) and isinstance(var_value[0], list):
                # Still a nested list; assign back for further unpacking
                new_variables[var_name] = var_value
            else:
                # Scalar value; set the parameter
                scalar_value = var_value[0]
                params_to_set[var_name] = scalar_value
                new_state[var_name] = scalar_value
                new_variables.pop(var_name)

        if params_to_set:
            set_parameters(params_to_set)

        # Recursive call with updated variables and state
        run_experiment(new_variables, new_state)

# Example usage
if __name__ == "__main__":
    # Define the experiment variables
    variables = {
        'T': 45,
        'B': [-100, 100],
        'B_sweep': [[0, 1, 2], [0, -1, -2]],
        'V': [[-1, 1]]
    }

    run_experiment(variables)
