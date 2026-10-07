from datetime import datetime, timezone

from live_metrics.app import MAXLEN, create_app
from live_metrics.metrics import MetricsStream, kpis, p95


def fixed_clock():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def client(**kwargs):
    return create_app(seed=1, **kwargs).test_client()


def test_seeded_stream_is_deterministic():
    a = MetricsStream(seed=1, prefill=10, clock=fixed_clock)
    b = MetricsStream(seed=1, prefill=10, clock=fixed_clock)
    assert a.window(10) == b.window(10)


def test_stream_is_bounded():
    s = MetricsStream(seed=1, maxlen=5, prefill=20, clock=fixed_clock)
    assert len(s.window(100)) == 5


def test_p95_and_kpis():
    assert p95(range(1, 101)) == 95
    assert p95([]) == 0.0
    points = [{"requests": 10, "latency_ms": 1.0}, {"requests": 20, "latency_ms": 3.0}]
    assert kpis(points) == {"latest_requests": 20, "p95_latency_ms": 3.0}
    assert kpis([]) == {"latest_requests": 0, "p95_latency_ms": 0.0}


def test_api_metrics_window_and_keys():
    resp = client(prefill=100).get("/api/metrics?window=30")
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data) == 30
    assert set(data[0]) == {"ts", "cpu", "requests", "latency_ms"}


def test_api_metrics_rejects_bad_window():
    c = client()
    assert c.get("/api/metrics?window=0").status_code == 400
    assert c.get(f"/api/metrics?window={MAXLEN + 1}").status_code == 400


def test_health():
    assert client().get("/api/health").get_json() == {"status": "ok"}


def test_dash_layout_has_interval_and_graph():
    layout = str(client().get("/dash/_dash-layout").get_json())
    assert "Interval" in layout and "Graph" in layout


def test_dash_callback_refreshes_chart_and_kpis():
    server = create_app(seed=1, prefill=60)
    before = len(server.extensions["metrics_stream"].window(MAXLEN))
    payload = {
        "output": "..chart.figure...kpis.children..",
        "outputs": [
            {"id": "chart", "property": "figure"},
            {"id": "kpis", "property": "children"},
        ],
        "inputs": [
            {"id": "tick", "property": "n_intervals", "value": 1},
            {"id": "window", "property": "value", "value": 30},
        ],
        "changedPropIds": ["tick.n_intervals"],
    }
    resp = server.test_client().post("/dash/_dash-update-component", json=payload)
    assert resp.status_code == 200
    response = resp.get_json()["response"]
    assert "p95 latency" in response["kpis"]["children"]
    assert len(response["chart"]["figure"]["data"]) == 2
    assert len(server.extensions["metrics_stream"].window(MAXLEN)) == before + 1
