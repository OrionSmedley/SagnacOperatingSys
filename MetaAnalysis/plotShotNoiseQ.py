from matplotlib import pyplot as plt
filename = "ShotNoiseQ_1.csv"
import pandas as pd


# Plot the file sensitivities as a function of light intensity
plotable = pd.read_csv(filename)
plt.figure()
plt.plot(plotable.LightIntensity, plotable.xSensitivity, 'o', label='X Sensitivity'
            , color='blue')
plt.plot(plotable.LightIntensity, plotable.ySensitivity, 'o', label='Y Sensitivity'
            , color='red')
plt.xlabel('Light Intensity (nW)')
plt.ylabel('Sensitivity (V/sqrtHz)')
plt.legend()