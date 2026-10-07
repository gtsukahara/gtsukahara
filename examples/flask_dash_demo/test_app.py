from app import SALES, create_app


def client():
    return create_app().test_client()


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
