import dash_bootstrap_components as dbc
import pytest

from examples.flask_dash_demo.app import SALES, create_app


def client(**kwargs):
    return create_app(**kwargs).test_client()


def test_index():
    assert b"Flask + Dash demo" in client().get("/").data


def test_api_returns_all_rows():
    resp = client().get("/api/sales")
    assert resp.status_code == 200
    assert len(resp.get_json()) == len(SALES)


def test_dash_is_mounted():
    c = client()
    assert c.get("/dash/").status_code == 200
    layout = c.get("/dash/_dash-layout").get_json()
    assert "Revenue by month" in str(layout)


def test_landing_and_dash_use_the_chosen_theme():
    c = client(theme="flatly")
    assert dbc.themes.FLATLY in c.get("/").get_data(as_text=True)
    assert dbc.themes.FLATLY in c.get("/dash/").get_data(as_text=True)


def test_unknown_theme_is_rejected():
    with pytest.raises(ValueError, match="unknown theme"):
        create_app(theme="neon")


@pytest.mark.parametrize("region,expected_traces", [("All", 2), ("North", 1)])
def test_dash_callback_filters_by_region(region, expected_traces):
    payload = {
        "output": "chart.figure",
        "outputs": {"id": "chart", "property": "figure"},
        "inputs": [{"id": "region", "property": "value", "value": region}],
        "changedPropIds": ["region.value"],
    }
    resp = client().post("/dash/_dash-update-component", json=payload)
    assert resp.status_code == 200
    assert len(resp.get_json()["response"]["chart"]["figure"]["data"]) == expected_traces


def test_chart_uses_the_shared_palette():
    from examples.theme import COLORWAY

    payload = {
        "output": "chart.figure",
        "outputs": {"id": "chart", "property": "figure"},
        "inputs": [{"id": "region", "property": "value", "value": "All"}],
        "changedPropIds": ["region.value"],
    }
    data = client().post("/dash/_dash-update-component", json=payload).get_json()["response"]["chart"]["figure"]["data"]
    assert [t["marker"]["color"] for t in data] == COLORWAY[:2]
