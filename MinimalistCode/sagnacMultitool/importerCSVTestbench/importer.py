import numpy as np

def load_variables_from_csv(csv_file):
    with open(csv_file, 'r') as file:
        # Extract comment lines and remove the leading '#' and any whitespace
        comment_lines = [line.lstrip('#').strip() for line in file if line.startswith('#')]
    
    # Combine the comment lines into a single string
    comment_str = ' '.join(comment_lines)
    print("Executing the following parameters:")
    print(comment_str)

    input("Press Enter to continue...")

    # Define a namespace dictionary for exec, including numpy if needed
    namespace = {'np': np}

    # Execute the combined string within the namespace
    exec(comment_str, namespace)
    
    # Retrieve and return the 'parameters' dictionary from the namespace
    if 'parameters' in namespace:
        return namespace['parameters']
    else:
        raise ValueError("The 'parameters' dictionary was not found in the CSV comments.")

# Example usage
if __name__ == "__main__":
    parameters = load_variables_from_csv("initial.csv")
    print("Loaded parameters:", parameters)
