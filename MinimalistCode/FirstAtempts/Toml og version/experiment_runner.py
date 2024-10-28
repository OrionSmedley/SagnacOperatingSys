import tomllib

def load_config(toml_path):
    """Load and parse the TOML configuration file using tomllib."""
    with open(toml_path, 'rb') as f:
        config = tomllib.load(f)
    return config

def get_ordered_sweeps(sweeps):
    """Retrieve sweeps in the order they appear in the TOML file."""
    return sweeps.items()

def generate_nested_experiments(sorted_sweeps):
    """Generate nested experiments based on the sorted sweeps."""
    def recurse(current_params, remaining_sweeps):
        if not remaining_sweeps:
            yield current_params
            return
        sweep_name, sweep = remaining_sweeps
        sweep_type = sweep.get('type', 'sweep')
        if sweep_type == 'sweep':
            # Iterate over each value in the sweep
            for value in sweep['values']:
                new_params = current_params.copy()
                new_params[sweep_name] = value
                # Proceed to next sweep
                yield from recurse(new_params, remaining_sweeps[1:])
        else:
            raise ValueError(f"Unknown sweep type: {sweep_type}")
    return recurse({}, sorted_sweeps)

def run_experiment(parameters):
    """Execute the experiment and record the parameters."""
    # Check if 'V_init' is in parameters and handle initialization
    if 'V_init' in parameters:
        # Perform initialization: set V = V_init
        V_init = parameters.pop('V_init')
        print(f"Initializing with parameters: {{'V': {V_init}}}")
        # Optionally, you can store or use V_init as needed
    print(f"Running experiment with parameters: {parameters}")
    # Simulate experiment execution and data recording
    # For demonstration, we'll just pass
    pass

def main(config_path):
    config = load_config(config_path)
    sweeps = config.get('sweeps', {})
    sorted_sweeps = get_ordered_sweeps(sweeps)
    experiment_generator = generate_nested_experiments(sorted_sweeps)

    for params in experiment_generator:
        run_experiment(params)

if __name__ == "__main__":
    config_file = 'config.toml'
    main(config_file)
