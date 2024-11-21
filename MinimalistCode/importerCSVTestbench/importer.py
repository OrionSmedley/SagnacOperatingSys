import numpy as np
import sys

def load_variables_from_csv(csv_file):
    with open(csv_file, 'r') as file:
        # Extract comment lines and remove the leading '#' and any whitespace
        comment_lines = [line.lstrip('#').strip() for line in file if line.startswith('#')]
    
    comment_str = ' '.join(comment_lines)  # multiline comments -> single string
    print("Executing csv code: \n\t", comment_str)

    namespace = {'np': np} # modules for he exec namespace
    exec(comment_str, namespace) # Execute the combined string in namespace
    return namespace['parameters']

if __name__ == "__main__":
    # Get the CSV file path from the first command-line argument
    csv_file = sys.argv[1]
    
    # Load and process the CSV file
    result = load_variables_from_csv(csv_file)
    for key in result:
        print(key, result[key])
