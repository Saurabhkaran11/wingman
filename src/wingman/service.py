"""The brief pipeline, shared by the CLI and the web UI.

Everything after the agent hands back a Dossier is ordinary code, on purpose:
rendering, emailing and writing corrections back to the brain must happen on
every run, not when a model remembers to call a tool.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from wingman import actions, brain, config, events, sandbox
from wingman.calendar_reader import external_meetings
from wingman.models import Dossier, Meeting

SLUG_RE = re.compile(r"^[a-z0-9_]{1,80}$")


class NoMeetings(RuntimeError):
    """No upcoming meeting has an attendee other than the user."""


def calendar_source(override: str = "") -> str:
    """Where the calendar comes from: an override, WINGMAN_CALENDAR, or the sample."""
    return override or config.env("WINGMAN_CALENDAR", str(config.ROOT / "data/sample/calendar.ics"))


def select_meeting(calendar: str = "", person: str = "", company: str = "") -> Meeting:
    """The meeting to brief on: a named person, or the next one on the calendar.

    Example: select_meeting(person="Priya Shah", company="Cognee")
      -> Meeting(title="Meeting with Priya Shah (Cognee)", attendees=["Priya Shah (Cognee)"])
    """
    if person:
        who = f"{person} ({company})" if company else person
        return Meeting(title=f"Meeting with {who}", start=datetime.now(timezone.utc).isoformat(), attendees=[who])
    meetings = upcoming(calendar)
    if not meetings:
        raise NoMeetings("no upcoming meetings with an external attendee")
    return meetings[0]


def upcoming(calendar: str = "") -> list[Meeting]:
    """Every future meeting with an external attendee, soonest first."""
    return external_meetings(calendar_source(calendar))


def dossier_path(slug: str, suffix: str) -> Path:
    """A path inside out/ for this person, with the slug validated.

    The slug reaches this from an HTTP request, so it is checked against a
    strict pattern rather than trusted. Anything else cannot name a file.
    Example: dossier_path("priya_shah", "pdf") -> out/dossier_priya_shah.pdf
    """
    if not SLUG_RE.match(slug):
        raise ValueError(f"invalid dossier name: {slug!r}")
    return config.OUT_DIR / f"dossier_{slug}.{suffix}"


def saved_dossiers() -> list[dict]:
    """Every dossier already on disk, newest first, for the dashboard's list.

    A file someone hand-edited into invalid JSON is skipped, not fatal.
    """
    out = []
    for path in sorted(config.OUT_DIR.glob("dossier_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            dossier = Dossier.model_validate_json(path.read_text())
        except Exception:
            continue
        slug = path.stem.removeprefix("dossier_")
        out.append({
            "slug": slug,
            "person": dossier.person,
            "role": dossier.role,
            "company": dossier.company,
            "updated": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            "has_pdf": dossier_path(slug, "pdf").exists(),
            "counts": {
                "i_owe_them": len(dossier.i_owe_them),
                "they_owe_me": len(dossier.they_owe_me),
                "stale_alerts": len(dossier.stale_alerts),
                "whats_new": len(dossier.whats_new),
            },
        })
    return out


def load_dossier(slug: str) -> Dossier:
    return Dossier.model_validate_json(dossier_path(slug, "json").read_text())


def run_brief(meeting: Meeting, writeback: bool = True) -> dict:
    """Research the meeting, render it, send it, and correct the brain.

    Emits progress to the active run (see events.py) so the CLI can print it and
    the browser can stream it. Returns a summary dict.

    Example: run_brief(meeting) -> {"slug": "priya_shah", "pdf": "out/...pdf",
                                    "email": "emailed dossier to you@gmail.com", ...}
    """
    from wingman.agent import bright_data_client, prepare_dossier

    events.emit("step", "Next meeting", f"{meeting.title} with {meeting.attendees[0]}")

    # 1. Research: memory + live web -> a typed Dossier.
    events.emit("step", "Connecting", f"brain ({brain.connect()} mode) and Bright Data")
    with bright_data_client() as web:
        events.emit("step", "Agent is researching")
        dossier = prepare_dossier(meeting, web)

    # 2. Save the machine-readable and human-readable copies.
    slug = actions.slug(dossier.person)
    dossier_path(slug, "json").write_text(dossier.model_dump_json(indent=2))
    dossier_path(slug, "md").write_text(actions.to_markdown(dossier))

    # 3. Render the PDF in the sandbox. A render failure must not lose the run.
    events.emit("step", "Rendering PDF", "inside the Docker sandbox, no network")
    pdf = None
    try:
        staged = sandbox.run_in_sandbox(dossier.model_dump())
        pdf = sandbox.collect(staged, dossier_path(slug, "pdf"))
        events.emit("result", "PDF rendered", config.show(pdf))
    except Exception as exc:
        events.emit("warn", "Sandbox render failed", f"{exc}. Continuing with Markdown only.")

    # 4. Act: the brief goes to the user, and only to the user.
    events.emit("step", "Sending the brief")
    email_status = actions.send_dossier_email(dossier, meeting.title, pdf)
    events.emit("result", "Brief sent", email_status)

    # 5. Learn: today's web facts supersede older notes, so next run is less stale.
    remembered = 0
    if dossier.whats_new and writeback:
        events.emit("step", "Writing new facts back into the brain")
        lines = [f"- {f.statement} (source: {f.source_url}, as of {f.as_of})" for f in dossier.whats_new]
        brain.remember(
            f"TYPE: web research\nDATE: {datetime.now().date()}\n"
            f"ABOUT: {dossier.person}, {dossier.company}\n\n"
            "Current public facts. These supersede older notes:\n" + "\n".join(lines)
        )
        remembered = len(lines)
        events.emit("result", "Brain updated", f"{remembered} corrections stored")

    return {
        "slug": slug,
        "person": dossier.person,
        "pdf": config.show(pdf) if pdf else None,
        "email": email_status,
        "remembered": remembered,
        "stale_alerts": len(dossier.stale_alerts),
        "i_owe_them": len(dossier.i_owe_them),
        "whats_new": len(dossier.whats_new),
    }


def brief_in_background(meeting: Meeting, writeback: bool = True) -> events.Run:
    """Start a brief on a worker thread and return its Run immediately.

    The web UI needs the run id straight away so the browser can open the event
    stream while the agent is still working.
    """
    import threading

    run = events.start(meeting.title)

    def work() -> None:
        # BaseException, not Exception: a SystemExit or KeyboardInterrupt raised
        # anywhere in the pipeline must still close the run and free the slot.
        try:
            events.end(run, result=run_brief(meeting, writeback=writeback))
        except BaseException as exc:
            events.end(run, error=f"{type(exc).__name__}: {exc}")

    threading.Thread(target=work, name=f"brief-{run.id}", daemon=True).start()
    return run
