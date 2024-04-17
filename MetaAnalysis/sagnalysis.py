
''' Functions for importing and analyzing data from the Sagnac interferometer. 

    if this file is in the same directory your python file, you can import these functions like this:
    import sagnalysis as sagn
    sagn.filter_files(file_paths, desired_start)
'''

import pandas as pd
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
import matplotlib.dates as mdates
from typing import List, Tuple

plt.rcParams["figure.dpi"] = 100

def parse_metadata(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    metadata = {}
    for line in lines:
        if line.startswith('#\t'):
            key, value = line.strip().split(': ')
            # metadata[key.strip()] = value.strip() 
            # This removes the anoying #\t in the beginning of the key
            metadata[key.strip().replace("#\t", "meta. ")] = value.strip()

    return metadata

def filter_files(file_paths:List[str] , 
                 desired_start:str = "#Procedure: <sagnac.procedures.HeterodyneProcedure.sagnacOpticsXportProcedure>"
                 ) -> Tuple[List[str], List[str]]:
    '''Filter files based on the first line of the file
    good_files are files that start with desired_start.

        Parameters:
            file_paths: list of file paths
            desired_start: desired start of the file
        
        Returns: good_files, bad_files

        Example usage: 
            the following code will return all bad_files that don't start with the desired_start
            desired_start = "#Procedure: <sagnac.procedures.HeterodyneProcedure.sagnacOpticsXportProcedure>"
            file_paths = Path(path).rglob('*.csv')
            filter_files(file_paths, desired_start )[1]
    '''
    good_files = []
    bad_files = []
    for file_path in file_paths:
        with open(file_path) as f:
            if f.readline().startswith(desired_start):
                good_files.append(file_path)
            else:
                bad_files.append(file_path)
    return good_files, bad_files


def import_all_at_path(path: List[str] ,
                       desired_start:str = "#Procedure: <sagnac.procedures.HeterodyneProcedure.sagnacOpticsXportProcedure>",
                       filetype:str = "*.csv"
                       )-> List[str]:
    '''
    Import all csv files in a directory and its subdirectories into a single dataframe.
    By default The csv files must start with the line "#Procedure: <sagnac.procedures.HeterodyneProcedure.sagnacOpticsXportProcedure>"
    '''

    #get all files from all subdirectories
    files = Path(path).rglob(filetype)
    
    # restrict to files that begin with "#Procedure: <sagnac.procedures.HeterodyneProcedure.sagnacOpticsXportProcedure>"
    files = filter_files(files, desired_start=desired_start)[0]


    # collect dataframes for all files in a list
    data = []
    for file in files:
        # read the data from the csv file
        filedata = pd.read_csv(file, comment="#") # alternative: print(os.path.basename(file))

        # Add metadata from comments to the dataframe
        metadata = parse_metadata(file)
        for key, value in metadata.items():
            filedata[key] = value
        
        # Add the time the file was last modified
        timestamp = os.path.getmtime(file)
        date =  datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') # convert timestamp to date string
        filedata["timeModified"] = timestamp
        filedata["dateModified"] = date


        # Add filename to the dataframe
        if "filename" in filedata.columns:
            raise Exception( "goofed: filename exists already" )
        filedata["filename"] = os.path.basename(file)
        if "filepath" in filedata.columns:
            raise Exception( "goofed: filename exists already" )
        filedata["filepath"] =  file

        # Add the data to the list of dataframes
        data.append(filedata )

    # concatenate all dataframes in the list
    return pd.concat(data, axis=0) # axis=0 means row wise concatenation


def plot_power_for_dir(dir_path):
    lumped_data = import_all_at_path(dir_path)
    plot_power_for_df(lumped_data)

def plot_power_for_df(lumped_data,hrsPerTick=4):
    plotable = lumped_data.groupby("filepath").mean()[["X2", "Y2","timeModified"]]
    plotable['timeModified'] = pd.to_datetime(plotable['timeModified'], unit='s')
    plotable = plotable.sort_values(by="timeModified")
    plt.plot(plotable.timeModified, plotable.X2 * 1e3, label="X2",marker="x")
    plt.plot(plotable.timeModified, plotable.Y2 * 1e3, label="Y2",marker="x")


    # Set the x-axis labels to be displayed every 24 hours
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=hrsPerTick))
    plt.gcf().autofmt_xdate()

    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xlabel("Time")
    plt.ylabel("Second Harmonic Power (mv)")




# function for data where everything is anoyingly in one column
# commented out because it is not used, for now

# def reshape_column_into_data(data:pd.DataFrame)->pd.DataFrame:
#     ''' Split the masive column into each variable measured
#     '''
#     data.columns = ["Time","Voltage"]

#     data['Group'] = ( data['Time'] == 0).cumsum()
#     data.loc[data["Time"]==0, "Group"] = data.loc[data["Time"]==0, "Group"] - 1

#     data = data.pivot_table(index = "Time",columns="Group", values = "Voltage", aggfunc = "mean")
#     data.columns = ["x1","y1","x2","y2"]

#     return data