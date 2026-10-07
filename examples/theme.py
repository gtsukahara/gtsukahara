"""Shared look for the example apps.

One Bootswatch theme (dash-bootstrap-components), the matching Plotly figure
template (dash-bootstrap-templates), a colour-blind-safe chart palette, and a
KPI card, so all three demos look like a set.

Pick a theme with the EXAMPLES_THEME environment variable (see THEMES) or
``create_app(theme=...)``.
"""
import os

import dash_bootstrap_components as dbc
from dash import html
from dash_bootstrap_templates import load_figure_template

# The 25 themes bundled with dash-bootstrap-components; each has a matching figure template.
THEMES = (
    "CERULEAN", "COSMO", "CYBORG", "DARKLY", "FLATLY", "JOURNAL", "LITERA", "LUMEN", "LUX",
    "MATERIA", "MINTY", "MORPH", "PULSE", "QUARTZ", "SANDSTONE", "SIMPLEX", "SKETCHY", "SLATE",
    "SOLAR", "SPACELAB", "SUPERHERO", "UNITED", "VAPOR", "YETI", "ZEPHYR",
)
DEFAULT_THEME = "DARKLY"

# Okabe-Ito colours (colour-blind safe). Set explicitly because some themes' own
# palettes are low contrast on their background (DARKLY's first colour is dark blue).
COLORWAY = ["#56B4E9", "#E69F00", "#009E73", "#F0E442", "#CC79A7", "#D55E00"]


def theme_from_env() -> str:
    return os.environ.get("EXAMPLES_THEME", DEFAULT_THEME)


def resolve_theme(theme: str):
    """Validate ``theme``; return (stylesheet URL, figure template name)."""
    name = theme.upper()
    if name not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; choose one of {', '.join(THEMES)}")
    template = name.lower()
    load_figure_template(template)
    return getattr(dbc.themes, name), template


def style_figure(fig, template: str):
    """Apply the theme's template and palette, with margins that suit narrow screens.

    Axes size their own margins to fit their labels (``automargin``), the outer margins are small, and
    the legend sits above the plot instead of beside it, so phones keep most of the width for the data.
    """
    has_title = bool(fig.layout.title.text)
    fig.update_layout(
        template=template,
        colorway=COLORWAY,
        margin={"l": 8, "r": 8, "t": 90 if has_title else 40, "b": 8},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    return fig


def graph_card(graph):
    """A card around a dcc.Graph, with tighter padding on phones."""
    return dbc.Card(dbc.CardBody(graph, className="p-1 p-md-3"))


def kpi_card(label: str, value: str):
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(label, className="text-muted small"),
                    html.H3(value, className="mb-0"),
                ]
            )
        ),
        xs=6,
        md=3,
    )
