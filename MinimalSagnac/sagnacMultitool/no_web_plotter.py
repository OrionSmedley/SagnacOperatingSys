import pandas as pd
import plotly.graph_objects as go
from IPython.display import clear_output, display
import time


class DynamicPlotter:
    def __init__(self, file_path):
        self.file_path = file_path
        self.cached_data = None
        self.x_axis = None
        self.y_axis = None
        self.color = None

        # Load initial data
        self._load_initial_data()

    def _load_initial_data(self):
        """Loads the initial data from the CSV and sets default columns."""
        self.cached_data = self._rename_columns(pd.read_csv(self.file_path, comment=";"))
        if len(self.cached_data.columns) >= 2:
            self.x_axis = self.cached_data.columns[0]
            self.y_axis = self.cached_data.columns[1]
        else:
            raise ValueError("CSV must have at least two columns for plotting.")

    @staticmethod
    def _rename_columns(df):
        """Renames columns by stripping prefixes or unnecessary parts."""
        df.columns = [col.split('#')[-1].strip() if '#' in col else col.strip() for col in df.columns]
        return df

    def set_axes(self, x_axis, y_axis, color=None):
        """Sets the columns for the X-axis, Y-axis, and optional color."""
        if x_axis in self.cached_data.columns and y_axis in self.cached_data.columns:
            self.x_axis = x_axis
            self.y_axis = y_axis
            self.color = color if color in self.cached_data.columns else None
        else:
            raise ValueError("Specified columns must exist in the CSV data.")

    def _plot_data(self):
        """Plots the data using Plotly."""
        fig = go.Figure()

        # Add scatter plot trace
        fig.add_trace(
            go.Scatter(
                x=self.cached_data[self.x_axis],
                y=self.cached_data[self.y_axis],
                mode='lines+markers',
                marker=dict(color=self.cached_data[self.color]) if self.color else None,
            )
        )

        # Update layout
        fig.update_layout(
            title=f"Dynamic Plot for {self.file_path}",
            xaxis_title=self.x_axis,
            yaxis_title=self.y_axis,
            template="plotly_white",
            legend_title=None,  # No separate legend entries
        )

        # Add label for color variable on the side
        if self.color:
            fig.add_annotation(
                text=self.color,
                xref="paper",
                yref="paper",
                x=1.05,  # Position outside the plot area
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="black"),
                align="center",
            )

        # Display the figure
        clear_output(wait=True)
        display(fig)

    def start_auto_refresh(self, interval=1):
        """Starts auto-refreshing the plot."""
        try:
            print("Starting auto-refresh. Stop the cell to end.")
            while True:
                # Reload data
                new_data = self._rename_columns(pd.read_csv(self.file_path, comment=";"))

                # Append only new rows to cached data
                if len(new_data) > len(self.cached_data):
                    self.cached_data = pd.concat(
                        [self.cached_data, new_data.iloc[len(self.cached_data):]],
                        ignore_index=True
                    )

                # Plot the updated data
                self._plot_data()

                # Wait before refreshing
                time.sleep(interval)
        except KeyboardInterrupt:
            print("Auto-refresh stopped.")
