# Running and sharing the demo apps

Three small Flask + Dash apps live here. Each has its own README with details;
this page covers running them locally and putting one online.

**New to this? Start with `flask_dash_demo`**: it is the simplest (one short file) and the quickest way to see
how Flask and Dash fit together. `live_metrics` adds auto-refresh; `task_tracker` adds a database and forms.

| Demo | What it shows | Local port |
|---|---|---|
| `flask_dash_demo` | Simplest: Dash mounted on a Flask server, pandas-backed API | 5003 |
| `live_metrics` | Self-refreshing dashboard over a simulated metrics API | 5001 |
| `task_tracker` | Flask + SQLAlchemy CRUD API with a Dash stats page | 5002 |

## 1. Run locally

Use Python 3.11 (the repo pins it in `.python-version`; with pyenv, `pyenv install 3.11` first if needed).

```bash
git clone https://github.com/gtsukahara/gtsukahara.git
cd gtsukahara
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run one demo from the repo root:

```bash
python -m examples.live_metrics.app      # http://127.0.0.1:5001/dash/
python -m examples.task_tracker.app      # http://127.0.0.1:5002/dash/
python -m examples.flask_dash_demo.app    # http://127.0.0.1:5003/  (dashboard at /dash/)
```

Run the tests (all demos at once, or one folder):

```bash
pytest examples
pytest examples/task_tracker
```

Notes:
- **Port 5000 on macOS:** the AirPlay Receiver uses it, which is why the demos use ports 5001-5003. If you run
  your own Flask app on 5000, pick another port or turn off System Settings > General > AirDrop & Handoff >
  AirPlay Receiver.
- `task_tracker` creates `tasks.db` in the directory you run it from (git-ignored) and seeds sample tasks if it is empty.
- `requirements.txt` is the whole repo's pin list (Django, FastAPI, etc.), so the install is large.
  The demos only need: `flask`, `dash`, `plotly`, `pandas`, `sqlalchemy`, `gunicorn`.

## 2. Run it the way a host will (gunicorn)

Debug mode (`app.run(debug=True)`) is for development only. Hosts run a production server instead.
These commands were tested locally; each serves the API and `/dash/`:

```bash
gunicorn "examples.live_metrics.app:create_app()"  --workers 1 --threads 4 --bind 127.0.0.1:8000
gunicorn "examples.task_tracker.app:create_app()"  --workers 1 --threads 4 --bind 127.0.0.1:8000
gunicorn "examples.flask_dash_demo.app:create_app()" --workers 1 --threads 4 --bind 127.0.0.1:8000
```

Keep `--workers 1`:
- `live_metrics` keeps its stream in memory per process. With several workers, each poll can hit a
  different worker and the chart will jump around.
- `task_tracker` uses a SQLite file, which is fine for one worker but not for many.

When deployed there is no `__main__`, so `task_tracker` starts **empty** (it only seeds sample data when run with
`python -m ...`). Add tasks through the form on `/dash/` or `POST /api/tasks`.

## 3. Share it

### Option A: temporary public link (fastest, minutes)
Good for showing someone for an hour. Your laptop must stay on and the app running.

```bash
brew install cloudflared
python -m examples.live_metrics.app                       # terminal 1
cloudflared tunnel --url http://localhost:5001            # terminal 2
```

`cloudflared` prints an `https://<random>.trycloudflare.com` URL. Send them `<url>/dash/`.
(`ngrok http 5001` works the same way but needs a free account.) Anyone with the URL can reach the app, so do not
expose anything private, and stop the tunnel when you are done.

### Option B: hosted web service (always on, shareable URL)
Render is one of several hosts with a free tier (Railway and Fly.io are similar). Steps for Render:

1. Push this repo to GitHub (done) and sign in at render.com with GitHub.
2. New > **Web Service** > pick `gtsukahara/gtsukahara`.
3. Settings:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn "examples.live_metrics.app:create_app()" --workers 1 --threads 4`
     (swap in the `task_tracker` or `flask_dash_demo` line for those)
   - **Environment variable:** `PYTHON_VERSION` set to a full 3.11.x version Render supports
     (their docs list the supported versions)
4. Deploy. Render builds, runs the start command and gives you `https://<name>.onrender.com`; open `/dash/`.
   It binds to Render's `PORT` automatically because gunicorn reads that variable.

Things to know about free tiers (check the host's current terms; they change):
- Free services usually sleep after a period of inactivity, so the first visit can take around a minute.
- Disk is usually ephemeral: `task_tracker`'s `tasks.db` resets on each deploy or restart. For data that
  must persist, point `create_app(db_url=...)` at a hosted Postgres and add its driver to the requirements.
- One demo per service. To share all three, create three services.
- The app is public by default. There is no login in these demos; do not put real data in them.

To speed up builds, consider a slim `requirements-demo.txt` with only the packages listed above and use it as the
build command's file.
