import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, Input, Output
import dash
import sys

# Function to rename columns
def rename_columns(df):
    df.columns = [col.split('#')[-1].strip() if '#' in col else col.strip() for col in df.columns]
    return df

# Ensure a file path is provided
if len(sys.argv) != 2:
    print("Usage: python plotter.py path/to/data.csv")
    sys.exit(1)

# File path from the command line
file_path = sys.argv[1]

# Load initial data
data = rename_columns(pd.read_csv(file_path, comment=";"))

# Initialize Dash app
app = dash.Dash(__name__)
app.title = "Dynamic File Plotter"

# Cache to track new rows
cached_data = data.copy()

# Layout
app.layout = html.Div([
    html.H1("Dynamic CSV Plotter", style={"textAlign": "center"}),

    # Dropdown menus
    html.Div([
        html.Label("X-axis:"),
        dcc.Dropdown(
            id='x-axis',
            options=[{"label": col, "value": col} for col in cached_data.columns],
            value=cached_data.columns[0]
        ),
        html.Label("Y-axis:"),
        dcc.Dropdown(
            id='y-axis',
            options=[{"label": col, "value": col} for col in cached_data.columns],
            value=cached_data.columns[1]
        ),
        html.Label("Color:"),
        dcc.Dropdown(
            id='color',
            options=[{"label": col, "value": col} for col in cached_data.columns],
            value=None
        ),
    ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),

    # Graph
    dcc.Graph(id="line-plot"),

    # Interval for auto-refresh
    dcc.Interval(id="interval-update", interval=20*1000, n_intervals=0),
])

# Callback to update the graph dynamically
@app.callback(
    Output("line-plot", "figure"),
    [Input("x-axis", "value"),
     Input("y-axis", "value"),
     Input("color", "value"),
     Input("interval-update", "n_intervals")]
)
def update_graph(x_axis, y_axis, color, n_intervals):
    global cached_data

    # Reload data
    new_data = rename_columns(pd.read_csv(file_path, comment=";"))

    # Check for new rows and append them
    if len(new_data) > len(cached_data):
        cached_data = pd.concat([cached_data, new_data.iloc[len(cached_data):]], ignore_index=True)

    # Create and return the updated figure
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=cached_data[x_axis],
            y=cached_data[y_axis],
            mode='lines+markers',
            marker=dict(color=cached_data[color]) if color else None
        )
    )
    fig.update_layout(
        title=f"Plot for {file_path}",
        xaxis_title=x_axis,
        yaxis_title=y_axis
    )
    return fig

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)