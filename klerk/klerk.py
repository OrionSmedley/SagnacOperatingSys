import plotly.express as px
# import pandas as pd
# import numpy as np

def export_fig(fig, filename, width=600, height=600*3/4):
    fig.update_layout(template="simple_white")
    fig.update_xaxes(showline=True, mirror=True, linecolor="black", linewidth=1)
    fig.update_yaxes(showline=True, mirror=True, linecolor="black", linewidth=1)
    # fig.update_layout(font=dict(size=14))
    fig.write_image(filename, width=width, height=height)
    print(f"Figure saved as {filename}")
    fig.show()




    
import copy
import plotly.io as pio

def _register_white_boxed():
    """
    Make a new template 'white_boxed' based on plotly_white
    with a thin black box around the axes.
    """
    tpl = copy.deepcopy(pio.templates["plotly_white"])
    for ax in ("xaxis", "yaxis"):
        # get any existing axis‑settings, or start fresh
        axis_layout = getattr(tpl.layout, ax) or {}
        axis_layout.update(
            showline=True,
            mirror=True,
            linecolor="black",
            linewidth=1
        )
        setattr(tpl.layout, ax, axis_layout)

    # register under your chosen name
    pio.templates["white_boxed"] = tpl

# auto‑register on import
_register_white_boxed()