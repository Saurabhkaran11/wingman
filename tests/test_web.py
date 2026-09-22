"""Scenario tests for the dashboard API.

No API keys needed: the two key-gated pieces (the LLM agent and the Cognee
brain) are mocked, and everything else — routing, validation, concurrency,
the event stream, the file handling — runs for real.

    uv run pytest tests/test_web.py -q
"""

import json
import subprocess
import threading
import time
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from wingman import config, events, service
from wingman.models import Dossier
from wingman.web.app import app

ROOT = config.ROOT
DOSSIER = Dossier.model_validate_json((ROOT / "examples" / "sample_dossier.json").read_text())
docker_up = subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_runs():
    """Every test starts with no run in flight, so the 409 guard is deterministic."""
    events._active = None
    events._runs.clear()
    yield
    events._active = None


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    """Point OUT_DIR at a temp folder so tests never touch the real out/."""
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)
    monkeypatch.setattr(config, "SMTP_USER", "")
    return tmp_path


def mocked_agent(dossier: Dossier = DOSSIER):
    """Replace only the pieces that need credentials."""
    from wingman import brain

    return [
        mock.patch.object(brain, "connect", return_value="mock"),
        mock.patch.object(brain, "remember"),
        mock.patch("wingman.agent.bright_data_client", return_value=mock.MagicMock()),
        mock.patch("wingman.agent.prepare_dossier", return_value=dossier),
    ]


def wait_for_run(run_id: str, timeout: float = 30) -> events.Run:
    """Block until a background run finishes. Fails loudly instead of hanging."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = events.get(run_id)
        assert run is not None
        if run.state != "running":
            return run
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not finish within {timeout}s")


# ── health ────────────────────────────────────────────────────────────────

def test_health_reports_every_check(client):
    body = client.get("/api/health").json()
    names = [c["name"] for c in body["checks"]]
    assert names == ["Docker sandbox", "Calendar", "Cognee brain", "Bright Data web", "LLM", "Email"]
    assert all(c["state"] in {"pass", "skip", "fail"} for c in body["checks"])
    assert isinstance(body["ready"], bool)


def test_health_never_leaks_a_secret(client, monkeypatch):
    # Even with credentials configured, only states and hints go to the browser.
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-secret-value-do-not-leak")
    monkeypatch.setattr(config, "BRIGHT_DATA_TOKEN", "bd-secret-token-do-not-leak")
    monkeypatch.setattr(config, "SMTP_APP_PASSWORD", "hunter2hunter2")
    body = client.get("/api/health").text
    for secret in ("sk-ant-secret-value-do-not-leak", "bd-secret-token-do-not-leak", "hunter2hunter2"):
        assert secret not in body


# ── meetings ──────────────────────────────────────────────────────────────

def test_meetings_lists_external_only(client):
    body = client.get("/api/meetings").json()
    titles = [m["title"] for m in body["meetings"]]
    assert "Team standup" not in titles          # I am its only attendee
    assert body["source"] == "local file"
    assert all(m["attendees"] for m in body["meetings"])


def test_meetings_reports_a_broken_calendar(client, monkeypatch):
    monkeypatch.setattr(service, "upcoming", mock.Mock(side_effect=OSError("feed is down")))
    response = client.get("/api/meetings")
    assert response.status_code == 502 and "feed is down" in response.json()["detail"]


# ── dossiers ──────────────────────────────────────────────────────────────

def test_dossier_round_trip(client, out_dir):
    (out_dir / "dossier_priya_shah.json").write_text(DOSSIER.model_dump_json())
    listed = client.get("/api/dossiers").json()["dossiers"]
    assert listed[0]["slug"] == "priya_shah"
    assert listed[0]["counts"]["i_owe_them"] == 2
    assert client.get("/api/dossiers/priya_shah").json()["person"] == "Priya Shah"


def test_unreadable_dossier_is_skipped_not_fatal(client, out_dir):
    (out_dir / "dossier_good.json").write_text(DOSSIER.model_dump_json())
    (out_dir / "dossier_broken.json").write_text("{not json")
    slugs = [d["slug"] for d in client.get("/api/dossiers").json()["dossiers"]]
    assert slugs == ["good"]


def test_missing_dossier_is_404(client, out_dir):
    assert client.get("/api/dossiers/nobody").status_code == 404


@pytest.mark.parametrize("slug", ["../../etc/passwd", "..%2F..%2Fsecrets", "a/b", "$(whoami)", "x" * 200])
def test_slug_validation_blocks_path_tricks(client, slug):
    # Either the router refuses to match it, or the validator rejects it.
    assert client.get(f"/api/dossiers/{slug}").status_code in (400, 404)


def test_pdf_is_served_and_404s_when_absent(client, out_dir):
    (out_dir / "dossier_priya_shah.json").write_text(DOSSIER.model_dump_json())
    assert client.get("/api/dossiers/priya_shah/pdf").status_code == 404
    (out_dir / "dossier_priya_shah.pdf").write_bytes(b"%PDF-1.4 fake")
    response = client.get("/api/dossiers/priya_shah/pdf")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"


# ── running a brief ───────────────────────────────────────────────────────

@pytest.mark.skipif(not docker_up, reason="Docker daemon not running")
def test_brief_runs_end_to_end_and_streams(client, out_dir):
    with mocked_agent()[0], mocked_agent()[1], mocked_agent()[2], mocked_agent()[3]:
        started = client.post("/api/brief", json={"person": "Priya Shah", "company": "Cognee"})
        assert started.status_code == 202
        run_id = started.json()["run"]

        # The stream must replay history and end with a `done` event.
        with client.stream("GET", f"/api/runs/{run_id}/stream") as stream:
            body = "".join(chunk for chunk in stream.iter_text())

        run = wait_for_run(run_id)

    assert run.state == "done", run.error
    assert "event: done" in body
    kinds = {e["kind"] for e in run.events}
    assert {"step", "result"} <= kinds
    assert (out_dir / "dossier_priya_shah.json").exists()
    assert (out_dir / "dossier_priya_shah.pdf").exists()
    assert run.result["slug"] == "priya_shah"


def test_second_brief_while_one_runs_is_409(client):
    gate = threading.Event()

    def slow(*_args, **_kwargs):
        gate.wait(timeout=10)
        return DOSSIER

    from wingman import brain

    with mock.patch.object(brain, "connect", return_value="mock"), \
         mock.patch("wingman.agent.bright_data_client", return_value=mock.MagicMock()), \
         mock.patch("wingman.agent.prepare_dossier", side_effect=slow):
        first = client.post("/api/brief", json={"person": "Priya Shah"})
        assert first.status_code == 202
        second = client.post("/api/brief", json={"person": "Someone Else"})
        assert second.status_code == 409 and "already running" in second.json()["detail"]
        gate.set()
        wait_for_run(first.json()["run"])


def test_agent_failure_becomes_an_error_run_not_a_crash(client, out_dir):
    from wingman import brain

    with mock.patch.object(brain, "connect", return_value="mock"), \
         mock.patch("wingman.agent.bright_data_client", return_value=mock.MagicMock()), \
         mock.patch("wingman.agent.prepare_dossier", side_effect=RuntimeError("model refused")):
        run_id = client.post("/api/brief", json={"person": "Priya Shah"}).json()["run"]
        run = wait_for_run(run_id)

    assert run.state == "error" and "model refused" in run.error
    # The browser still gets a clean summary rather than a dropped connection.
    summary = client.get(f"/api/runs/{run_id}").json()
    assert summary["state"] == "error"
    assert summary["events"][-1]["kind"] == "error"


def test_brief_with_no_meetings_is_404(client, monkeypatch):
    monkeypatch.setattr(service, "upcoming", mock.Mock(return_value=[]))
    assert client.post("/api/brief", json={}).status_code == 404


def test_unknown_run_is_404(client):
    assert client.get("/api/runs/deadbeef").status_code == 404
    assert client.get("/api/runs/deadbeef/stream").status_code == 404


def test_active_run_lets_a_reloaded_page_rejoin(client):
    assert client.get("/api/runs").json()["run"] is None
    run = events.start("Coffee with Priya Shah")
    run.emit("step", "Agent is researching")
    body = client.get("/api/runs").json()["run"]
    assert body["id"] == run.id and body["events"][0]["text"] == "Agent is researching"
    events.end(run, result={})


def test_oversized_input_is_rejected(client):
    assert client.post("/api/brief", json={"person": "x" * 500}).status_code == 422


# ── the event bus itself ──────────────────────────────────────────────────

def test_subscriber_gets_history_then_live_events():
    run = events.start("test")
    run.emit("step", "first")
    queue = run.subscribe()          # subscribing late must not lose "first"
    run.emit("tool", "second")
    events.end(run, result={"ok": True})

    seen = []
    while True:
        item = queue.get(timeout=2)
        if events.is_done(item):
            break
        seen.append(item["text"])
    assert seen == ["first", "second"]


def test_a_broken_listener_cannot_kill_a_run():
    run = events.start("test")
    run.add_callback(lambda _event: (_ for _ in ()).throw(ValueError("listener exploded")))
    run.emit("step", "still fine")          # must not raise
    assert run.events[-1]["text"] == "still fine"
    events.end(run, result={})


def test_runs_registry_is_bounded():
    for index in range(events.MAX_RUNS_KEPT + 5):
        run = events.start(f"run {index}")
        events.end(run, result={})
    assert len(events._runs) == events.MAX_RUNS_KEPT


# ── the built UI ──────────────────────────────────────────────────────────

STATIC_BUILT = (Path(app.state.__dict__.get("_state", {}).get("static", "")) if False
                else (Path(__file__).parents[1] / "src/wingman/web/static/index.html")).exists()


@pytest.mark.skipif(not STATIC_BUILT, reason="frontend not built (cd frontend && npm run build)")
def test_dashboard_and_setup_pages_are_served(client):
    home = client.get("/")
    assert home.status_code == 200 and "<title>Wingman</title>" in home.text
    assert client.get("/setup/").status_code == 200


@pytest.mark.skipif(not STATIC_BUILT, reason="frontend not built")
def test_static_assets_do_not_shadow_the_api(client):
    # The SPA is mounted at "/" but must never intercept an /api route.
    assert client.get("/api/health").headers["content-type"].startswith("application/json")
