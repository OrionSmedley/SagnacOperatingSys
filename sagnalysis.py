import pandas as pd
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
import matplotlib.dates as mdates

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

def import_all_at_path(path):

    #get all files from all subdirectories
    files = Path(path).rglob('*.csv')

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
        date =  datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
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