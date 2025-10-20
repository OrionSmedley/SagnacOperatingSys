Install & use Guide
_______________________________
bash:

cd klerk
pip install -e .
_______________________________
Then in any script or notebook:

import klerk
from klerk import export_fig

# ... build your Plotly fig ...
export_fig(fig, "myplot.pdf")