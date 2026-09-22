"""Command-line entry point.

Commands:
  wingman web                        open the dashboard in a browser
  wingman doctor                     live-check every dependency (keys, Docker, web, model, email)
  wingman ingest <folder>            build the brain from a folder of .md/.txt/.eml files
  wingman ingest-gmail "<query>"     build the brain from live Gmail (read-only IMAP)
  wingman ask "<question>"           ask the brain a question directly
  wingman graph                      write an interactive HTML view of the knowledge graph
  wingman meetings                   list upcoming meetings with external attendees
  wingman brief --next               full run for the next meeting
  wingman brief --person "Name" --company "Co"
  wingman render <dossier.json>      render + email an existing dossier (offline; no LLM, no web)
  wingman reset                      wipe the brain's dataset
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from wingman import config


def _step(msg: str) -> None:
    # Bold cyan step headers double as live narration during the demo.
    print(f"\n\033[1;36m==> {msg}\033[0m")


def cmd_ingest(args) -> None:
    from wingman import brain
    from wingman.ingest import ingest_folder

    _step(f"Connecting to Cognee ({brain.connect()} mode), dataset '{config.DATASET}'")
    n = ingest_folder(Path(args.folder), brain.remember, limit=args.limit, delay=args.delay)
    print(f"\nremembered {n} documents")


def cmd_ingest_gmail(args) -> None:
    from wingman import brain
    from wingman.gmail_reader import fetch_emails

    _step(f"Fetching up to {args.limit} emails matching: {args.query}")
    emails = fetch_emails(args.query, args.limit)
    print(f"found {len(emails)} emails")
    if args.dry_run:
        # Show what WOULD be sent to the brain, so the user can check the filter first.
        for label, text in emails:
            print(f"--- {label}\n{text[:300]}\n")
        return
    _step(f"Connecting to Cognee ({brain.connect()} mode)")
    for i, (label, text) in enumerate(emails, 1):
        print(f"[{i}/{len(emails)}] remembering {label}")
        brain.remember(text)


def cmd_ask(args) -> None:
    from wingman import brain

    print(brain.recall(args.question))


def cmd_graph(args) -> None:
    from wingman import brain

    path = brain.visualize(str(config.OUT_DIR / "brain_graph.html"))
    print(f"graph written to {path}")


def cmd_meetings(args) -> None:
    from wingman.calendar_reader import external_meetings

    for m in external_meetings(args.calendar):
        print(f"{m.start}  {m.title}  ->  {', '.join(m.attendees)}")


def cmd_reset(args) -> None:
    from wingman import brain

    brain.forget_everything()
    print(f"dataset '{config.DATASET}' wiped")


def cmd_web(args) -> None:
    from wingman.web import serve

    serve(host=args.host, port=args.port, reload=args.reload)


def cmd_doctor(args) -> None:
    from wingman import doctor

    raise SystemExit(0 if doctor.run() else 1)


def cmd_render(args) -> None:
    # Offline path: proves the sandbox and email steps work without any API keys,
    # and re-renders a cached dossier if the venue Wi-Fi dies mid-demo.
    # Example: wingman render examples/sample_dossier.json -> out/dossier_priya_shah.pdf
    from wingman import actions, sandbox
    from wingman.models import Dossier

    dossier = Dossier.model_validate_json(Path(args.dossier).read_text())
    _step("Rendering PDF inside the Docker sandbox (no network)")
    staged = sandbox.run_in_sandbox(dossier.model_dump())
    pdf = sandbox.collect(staged, config.OUT_DIR / f"dossier_{actions.slug(dossier.person)}.pdf")
    print(f"wrote {config.show(pdf)}")
    _step("Sending the brief")
    print(actions.send_dossier_email(dossier, f"Meeting with {dossier.person}", pdf))


def cmd_brief(args) -> None:
    from wingman import actions, brain, sandbox
    from wingman.agent import bright_data_client, prepare_dossier
    from wingman.calendar_reader import external_meetings
    from wingman.models import Meeting

    started = time.time()

    # 1. Decide which meeting to prepare for.
    if args.person:
        who = f"{args.person} ({args.company})" if args.company else args.person
        meeting = Meeting(title=f"Meeting with {who}", start=datetime.now(timezone.utc).isoformat(), attendees=[who])
    else:
        meetings = external_meetings(args.calendar)
        if not meetings:
            raise SystemExit("no upcoming meetings with external attendees")
        meeting = meetings[0]
    _step(f"Next meeting: {meeting.title} with {meeting.attendees[0]}")

    # 2. Agent: memory + live web -> typed Dossier. Tool calls stream to the terminal.
    _step(f"Connecting brain ({brain.connect()} mode) and Bright Data")
    with bright_data_client() as web:
        _step("Agent is researching")
        dossier = prepare_dossier(meeting, web)

    # 3. Save the raw dossier and a readable Markdown copy.
    name = actions.slug(dossier.person)
    (config.OUT_DIR / f"dossier_{name}.json").write_text(dossier.model_dump_json(indent=2))
    (config.OUT_DIR / f"dossier_{name}.md").write_text(actions.to_markdown(dossier))

    # 4. Render the PDF inside the sandbox. A failure here must not lose the run.
    _step("Rendering PDF inside the Docker sandbox (no network)")
    pdf = None
    try:
        staged = sandbox.run_in_sandbox(dossier.model_dump())
        pdf = sandbox.collect(staged, config.OUT_DIR / f"dossier_{name}.pdf")
        print(f"wrote {config.show(pdf)}")
    except Exception as exc:
        print(f"sandbox render failed, continuing with Markdown only: {exc}")

    # 5. Act: email the brief to me.
    _step("Sending the brief")
    print(actions.send_dossier_email(dossier, meeting.title, pdf))

    # 6. Learn: write fresh web facts back so the brain is no longer stale next time.
    if dossier.whats_new and not args.no_writeback:
        _step("Writing new facts back into the brain")
        lines = [f"- {f.statement} (source: {f.source_url}, as of {f.as_of})" for f in dossier.whats_new]
        brain.remember(
            f"TYPE: web research\nDATE: {datetime.now().date()}\n"
            f"ABOUT: {dossier.person}, {dossier.company}\n\n"
            "Current public facts. These supersede older notes:\n" + "\n".join(lines)
        )
        print(f"remembered {len(lines)} new facts")

    _step(f"Done in {time.time() - started:.0f}s")
    print(json.dumps({"stale_alerts": len(dossier.stale_alerts), "i_owe_them": len(dossier.i_owe_them),
                      "web_facts": len(dossier.whats_new)}))


def main() -> None:
    parser = argparse.ArgumentParser(prog="wingman", description="The agent that briefs you before every meeting.")
    sub = parser.add_subparsers(dest="command", required=True)
    # Calendar source: a local .ics path or a live https iCal feed (WINGMAN_CALENDAR in .env).
    default_calendar = config.env("WINGMAN_CALENDAR", str(config.ROOT / "data/sample/calendar.ics"))

    p = sub.add_parser("ingest", help="remember every document in a folder")
    p.add_argument("folder")
    p.add_argument("--limit", type=int, help="stop after N documents (try --limit 1 first)")
    p.add_argument("--delay", type=float, default=0.0, help="seconds between documents, for rate-limited keys")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("ingest-gmail", help="remember live Gmail messages matching a search")
    p.add_argument("query", help='Gmail search, e.g. "from:priya@acme.com OR to:priya@acme.com newer_than:180d"')
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--dry-run", action="store_true", help="print matches without storing them")
    p.set_defaults(func=cmd_ingest_gmail)

    p = sub.add_parser("ask", help="ask the brain a question")
    p.add_argument("question")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("web", help="run the dashboard")
    p.add_argument("--host", default="127.0.0.1", help="bind address; Wingman has no login, so keep this local")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", help="reload on code changes (development)")
    p.set_defaults(func=cmd_web)

    sub.add_parser("doctor", help="live-check every dependency").set_defaults(func=cmd_doctor)
    sub.add_parser("graph", help="write out/brain_graph.html").set_defaults(func=cmd_graph)
    sub.add_parser("reset", help="wipe the brain's dataset").set_defaults(func=cmd_reset)

    p = sub.add_parser("meetings", help="list upcoming external meetings")
    p.add_argument("--calendar", default=default_calendar)
    p.set_defaults(func=cmd_meetings)

    p = sub.add_parser("render", help="render + email an existing dossier JSON (offline)")
    p.add_argument("dossier")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("brief", help="prepare, render and send a dossier")
    p.add_argument("--next", action="store_true", help="use the next meeting on the calendar (default)")
    p.add_argument("--person", help="skip the calendar and brief on this person")
    p.add_argument("--company", default="")
    p.add_argument("--calendar", default=default_calendar)
    p.add_argument("--no-writeback", action="store_true", help="do not store new web facts in the brain")
    p.set_defaults(func=cmd_brief)

    args = parser.parse_args()
    try:
        args.func(args)
    except config.MissingConfig as exc:
        raise SystemExit(f"{exc}\n\nRun `wingman doctor` to see everything that is missing.")
