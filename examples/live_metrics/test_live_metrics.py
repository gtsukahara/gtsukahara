from datetime import datetime, timedelta, timezone

from live_metrics.app import MAXLEN, create_app, kpi_cards, make_figure
from live_metrics.metrics import CPU_MEAN, STEP, MetricsStream, kpis, p95

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class Clock:
    """Settable clock so tests control how much time has passed."""

    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def client(**kwargs):
    return create_app(seed=1, **kwargs).test_client()


# --- stream ---------------------------------------------------------------

def test_seeded_stream_is_deterministic():
    a = MetricsStream(seed=1, prefill=10, clock=Clock())
    b = MetricsStream(seed=1, prefill=10, clock=Clock())
    assert a.window(10) == b.window(10)


def test_stream_is_bounded():
    s = MetricsStream(seed=1, maxlen=5, prefill=20, clock=Clock())
    assert len(s.window(100)) == 5


def test_prefill_is_one_point_per_second_ending_now():
    s = MetricsStream(seed=1, prefill=5, clock=Clock())
    stamps = [datetime.fromisoformat(p["ts"]) for p in s.window(5)]
    assert stamps[-1] == T0
    assert [b - a for a, b in zip(stamps, stamps[1:])] == [STEP] * 4


def test_advance_catches_up_without_gaps():
    clock = Clock()
    s = MetricsStream(seed=1, prefill=3, clock=clock)
    clock.advance(10)  # nobody polled for 10 seconds
    new = s.advance()
    assert len(new) == 10
    stamps = [datetime.fromisoformat(p["ts"]) for p in s.window(13)]
    assert [b - a for a, b in zip(stamps, stamps[1:])] == [STEP] * 12
    assert stamps[-1] == clock.now


def test_advance_is_idempotent_within_a_second():
    clock = Clock()
    s = MetricsStream(seed=1, prefill=3, clock=clock)
    clock.advance(0.5)
    assert s.advance() == []
    clock.advance(0.6)
    assert len(s.advance()) == 1
    assert s.advance() == []


def test_long_gap_only_keeps_the_newest_maxlen_points():
    clock = Clock()
    s = MetricsStream(seed=1, maxlen=50, prefill=0, clock=clock)
    clock.advance(10_000)
    new = s.advance()
    assert len(new) == 50
    assert datetime.fromisoformat(new[-1]["ts"]) == clock.now
    assert len(s.window(1000)) == 50


def test_cpu_reverts_to_mean_and_does_not_stick_at_100():
    clock = Clock()
    s = MetricsStream(seed=1, maxlen=6000, clock=clock)
    clock.advance(5000)
    s.advance()
    cpu = [p["cpu"] for p in s.window(6000)]
    assert abs(sum(cpu) / len(cpu) - CPU_MEAN) < 8
    assert sum(c >= 99.9 for c in cpu) / len(cpu) < 0.01
    assert min(cpu) >= 0 and max(cpu) <= 100


def test_p95_and_kpis():
    assert p95(range(1, 101)) == 95
    assert p95([]) == 0.0
    points = [{"requests": 10, "latency_ms": 1.0}, {"requests": 20, "latency_ms": 3.0}]
    assert kpis(points) == {"latest_requests": 20, "p95_latency_ms": 3.0}
    assert kpis([]) == {"latest_requests": 0, "p95_latency_ms": 0.0}


# --- API ------------------------------------------------------------------

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


# --- dashboard ------------------------------------------------------------

def test_figure_has_labelled_dual_axes():
    points = MetricsStream(seed=1, prefill=20, clock=Clock()).window(20)
    fig = make_figure(points)
    assert [t.name for t in fig.data] == ["CPU (%)", "Latency (ms)"]
    assert fig.layout.xaxis.title.text == "Time (UTC)"
    assert fig.layout.yaxis.title.text == "CPU (%)"
    assert fig.layout.yaxis2.title.text == "Latency (ms)"


def test_kpi_cards_show_both_values():
    text = str(kpi_cards({"latest_requests": 371, "p95_latency_ms": 241.2}))
    assert "371" in text and "241 ms" in text and "p95 latency" in text


def test_dash_layout_has_interval_graph_and_labelled_windows():
    layout = str(client().get("/dash/_dash-layout").get_json())
    assert "Interval" in layout and "Graph" in layout
    assert "Last 5 minutes" in layout


def test_dash_callback_catches_up_and_refreshes():
    clock = Clock()
    server = create_app(seed=1, prefill=60, clock=clock)
    stream = server.extensions["metrics_stream"]
    before = len(stream.window(MAXLEN))
    clock.advance(3)
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
    assert "p95 latency" in str(response["kpis"]["children"])
    assert len(response["chart"]["figure"]["data"]) == 2
    assert len(stream.window(MAXLEN)) == before + 3
