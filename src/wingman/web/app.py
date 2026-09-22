"""The Wingman dashboard: a small FastAPI app over the same pipeline the CLI runs.

Design rules this file sticks to:
  - No secret ever reaches the browser. /api/health returns states and hints only.
  - Every path built from a request is validated (service.dossier_path).
  - One brief at a time; a second request gets 409 rather than two agents racing.
  - Nothing here re-implements the pipeline: it all goes through wingman.service.
"""

import json
import queue
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wingman import config, doctor, events, service

STATIC = Path(__file__).parent / "static"
KEEPALIVE_SECONDS = 15  # a comment line so proxies do not close an idle stream

app = FastAPI(title="Wingman", version="0.1.0", docs_url="/api/docs")

# Only for `npm run dev`, where the UI is served from :3000 by Next's dev server.
# The shipped app is same-origin (FastAPI serves the built UI), so this is off
# unless WINGMAN_DEV=1 is set.
if config.env("WINGMAN_DEV") == "1":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


class BriefRequest(BaseModel):
    """What the dashboard sends to start a run."""

    person: str = Field("", max_length=120, description="Brief this person instead of the calendar's next meeting")
    company: str = Field("", max_length=120)
    writeback: bool = Field(True, description="Store the run's fresh web facts in the brain")


# ── read-only endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict:
    """Live dependency check, the same one `wingman doctor` prints.

    Returns states and human hints only — never a key, a token or a URL from .env.
    Example: {"ready": false, "checks": [{"name": "LLM", "state": "skip", "detail": "set ..."}]}
    """
    checks = doctor.status()
    blocking = {"Cognee brain", "Bright Data web", "LLM"}
    return {
        "checks": checks,
        # "ready" means a brief can actually run: the three that must work.
        "ready": all(c["state"] == "pass" for c in checks if c["name"] in blocking),
        "user": config.ME_NAME,
    }


@app.get("/api/meetings")
def meetings() -> dict:
    """Upcoming meetings with an external attendee, soonest first."""
    try:
        upcoming = service.upcoming()
    except Exception as exc:
        raise HTTPException(502, f"could not read the calendar: {exc}") from exc
    return {
        "source": "live feed" if service.calendar_source().startswith("https://") else "local file",
        "meetings": [m.model_dump() for m in upcoming],
    }


@app.get("/api/dossiers")
def dossiers() -> dict:
    """Every brief already on disk, newest first."""
    return {"dossiers": service.saved_dossiers()}


@app.get("/api/dossiers/{slug}")
def dossier(slug: str) -> dict:
    try:
        return service.load_dossier(slug).model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, f"no dossier named {slug}") from exc


@app.get("/api/dossiers/{slug}/pdf")
def dossier_pdf(slug: str) -> FileResponse:
    try:
        path = service.dossier_path(slug, "pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.exists():
        raise HTTPException(404, "no PDF for this dossier yet")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


# ── running a brief ─────────────────────────────────────────────────────────────────

@app.post("/api/brief")
def start_brief(request: BriefRequest) -> JSONResponse:
    """Kick off a brief and return its run id immediately.

    The browser then opens /api/runs/{id}/stream to watch it happen.
    """
    try:
        meeting = service.select_meeting(person=request.person.strip(), company=request.company.strip())
    except service.NoMeetings as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"could not pick a meeting: {exc}") from exc

    try:
        run = service.brief_in_background(meeting, writeback=request.writeback)
    except events.RunBusy as exc:
        raise HTTPException(409, str(exc)) from exc
    return JSONResponse({"run": run.id, "title": run.title}, status_code=202)


@app.get("/api/runs/{run_id}")
def run_summary(run_id: str) -> dict:
    """The whole run, including every event so far. Used on page reload."""
    run = events.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    return run.summary()


@app.get("/api/runs/{run_id}/stream")
def run_stream(run_id: str) -> StreamingResponse:
    """Server-Sent Events for one run: history first, then live events.

    A plain sync generator, so Starlette iterates it on a worker thread and the
    blocking queue read never stalls the event loop.
    """
    run = events.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")

    def stream() -> Iterator[str]:
        subscription = run.subscribe()
        try:
            while True:
                try:
                    item = subscription.get(timeout=KEEPALIVE_SECONDS)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                if events.is_done(item):
                    yield f"event: done\ndata: {json.dumps(run.summary())}\n\n"
                    return
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            # Always drop the queue, whether the run ended or the browser left.
            run.unsubscribe(subscription)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.get("/api/runs")
def current_run() -> dict:
    """Whichever run is going right now, so a reloaded page can rejoin it."""
    run = events.active()
    return {"run": run.summary() if run else None}


# The dashboard itself. Mounted last so it never shadows an /api route.
if (STATIC / "index.html").exists():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="dashboard")
else:
    @app.get("/", response_class=HTMLResponse)
    def missing_ui() -> str:
        """The API works; the UI was never built. Say exactly how to fix it."""
        return (
            "<!doctype html><meta charset=utf-8><title>Wingman</title>"
            "<body style=\"font-family:system-ui;max-width:40rem;margin:12vh auto;padding:0 1.5rem;line-height:1.6\">"
            "<h1>The dashboard has not been built yet</h1>"
            "<p>The API is running. Build the front end once, then reload this page:</p>"
            "<pre style=\"background:#f4f4f2;padding:1rem;border-radius:8px\">cd frontend &amp;&amp; npm install &amp;&amp; npm run build</pre>"
            "<p>API docs are at <a href=\"/api/docs\">/api/docs</a>.</p>"
        )


def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the dashboard.

    Binds to localhost by default: this app has no login, and it can read your
    mail and spend your API credits. Only pass another host on a network you
    trust, behind something that does authenticate.
    """
    import uvicorn

    if host not in ("127.0.0.1", "localhost"):
        print(f"\n  WARNING: binding to {host}. Wingman has no login — anyone who can reach\n"
              f"  this port can read your briefs and spend your API credits.\n")
    print(f"\n  Wingman dashboard -> http://{'localhost' if host == '127.0.0.1' else host}:{port}\n")
    uvicorn.run("wingman.web.app:app" if reload else app, host=host, port=port, reload=reload, log_level="warning")
