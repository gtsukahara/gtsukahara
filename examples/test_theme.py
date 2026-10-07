import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.io as pio
import pytest

from examples.theme import (
    COLORWAY, DEFAULT_THEME, THEMES, graph_card, kpi_card, resolve_theme, style_figure, theme_from_env,
)


@pytest.mark.parametrize("theme", THEMES)
def test_every_listed_theme_has_a_stylesheet_and_figure_template(theme):
    stylesheet, template = resolve_theme(theme)
    assert stylesheet == getattr(dbc.themes, theme) and stylesheet.startswith("http")
    assert template == theme.lower() and template in pio.templates


def test_theme_names_are_case_insensitive():
    assert resolve_theme("DaRkLy") == resolve_theme("DARKLY")


def test_default_theme_is_darkly_and_valid():
    assert DEFAULT_THEME == "DARKLY" and DEFAULT_THEME in THEMES


def test_unknown_theme_is_rejected():
    with pytest.raises(ValueError, match="unknown theme"):
        resolve_theme("neon")


def test_theme_from_env(monkeypatch):
    monkeypatch.delenv("EXAMPLES_THEME", raising=False)
    assert theme_from_env() == DEFAULT_THEME
    monkeypatch.setenv("EXAMPLES_THEME", "FLATLY")
    assert theme_from_env() == "FLATLY"


def test_style_figure_applies_template_and_palette():
    _, template = resolve_theme("DARKLY")
    fig = style_figure(go.Figure(go.Scatter(x=[1], y=[1])), template)
    assert list(fig.layout.colorway) == COLORWAY


def test_palette_is_distinct_hex_colours():
    assert len(set(COLORWAY)) == len(COLORWAY) >= 3
    assert all(c.startswith("#") and len(c) == 7 for c in COLORWAY)


def test_kpi_card_contains_label_and_value():
    text = str(kpi_card("Open", "7"))
    assert "Open" in text and "7" in text


def test_style_figure_keeps_margins_small_for_phones():
    _, template = resolve_theme("DARKLY")
    fig = style_figure(go.Figure(go.Scatter(x=[1], y=[1])), template)
    assert fig.layout.margin.l == fig.layout.margin.r == 8 and fig.layout.margin.b == 8
    assert fig.layout.xaxis.automargin and fig.layout.yaxis.automargin


def test_style_figure_puts_the_legend_above_the_plot():
    _, template = resolve_theme("DARKLY")
    legend = style_figure(go.Figure(go.Scatter(x=[1], y=[1])), template).layout.legend
    assert (legend.orientation, legend.yanchor, legend.y) == ("h", "bottom", 1.02)


def test_style_figure_leaves_more_top_room_when_there_is_a_title():
    _, template = resolve_theme("DARKLY")
    plain = style_figure(go.Figure(go.Scatter(x=[1], y=[1])), template)
    titled = style_figure(go.Figure(go.Scatter(x=[1], y=[1]), layout={"title": {"text": "Hi"}}), template)
    assert titled.layout.margin.t > plain.layout.margin.t


def test_style_figure_handles_figures_without_cartesian_axes():
    _, template = resolve_theme("DARKLY")
    style_figure(go.Figure(go.Pie(labels=["a"], values=[1])), template)  # must not raise


def test_graph_card_uses_tight_padding_on_small_screens():
    assert "p-1" in str(graph_card("graph")) and "p-md-3" in str(graph_card("graph"))
