import plotly.io as pio
import plotly.express as px
# import pandas as pd
# import numpy as np



def format_axes(fig, nticks_x=6, nticks_y=5, spine_width=1.5):
    """
    Draws a clean box with inside ticks and a fixed number of major ticks.
    """
    for updater, nt in ((fig.update_xaxes, nticks_x),
                        (fig.update_yaxes, nticks_y)):
        updater(
            showline=True, mirror="all", linecolor="black", linewidth=spine_width,
            ticks="inside", ticklen=6, tickwidth=1, tickcolor="black",
            showgrid=False, nticks=nt
        )
    return fig

def export_onecol(fig, filename,
                  width_pt=245,    # 3.4in × 72pt/in ≈ 245pt
                  aspect=3/4,
                  nticks_x=6,
                  nticks_y=5):
    """
    Formats axes for a one‑column RevTeX figure and exports as a vector PDF.
    
    - width_pt: target PDF width in points (1pt = 1/72in).
    - aspect : height/width ratio (default 4:3).
    - nticks_*: approximate number of major ticks on each axis.
    """
    # 1) apply axis formatting
    format_axes(fig, nticks_x=nticks_x, nticks_y=nticks_y)
    
    # 2) resize to exact PDF user units so LaTeX does no scaling
    w = int(width_pt)
    h = int(width_pt * aspect)
    fig.update_layout(
        width=w,
        height=h,
        margin=dict(l=50, r=20, t=20, b=50)
    )
    
    # 3) export vector PDF at exact size
    fig.write_image(filename, width=w, height=h)
    return fig


def export_fig(fig, filename, width=500, height=500*3/4):
    """ Exports a Plotly figure to a file with specified dimensions. human  code, it looks ok."""
    if height is None: height = width * 3 / 4
    fig.update_layout(template="simple_white")
    fig.update_xaxes(showline=True, mirror=True, linecolor="black", linewidth=1)
    fig.update_yaxes(showline=True, mirror=True, linecolor="black", linewidth=1)
    # fig.update_layout(font=dict(size=14))
    fig.write_image(filename, width=width, height=height)
    print(f"Figure saved as {filename}")
    fig.show()


import copy
def _register_white_boxed():
    """
    Make a new template 'white_boxed' based on plotly_white
    with a thin black box around the axes.
    GPT code. It looks ok.
    """
    tpl = copy.deepcopy(pio.templates["simple_white"])
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