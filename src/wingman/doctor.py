"""`wingman doctor`: check every live dependency before a demo.

Each check makes one small REAL call (a live web search, a one-word model
reply, an SMTP login) so a green row means the service works right now, not
just that a key is present.
"""

import shutil
import smtplib
import subprocess
import uuid
from typing import Callable

from wingman import config

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


class Skip(Exception):
    """Raised by a check when its keys are not configured yet."""


def check_docker() -> str:
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        raise RuntimeError("Docker daemon is not running. Start Docker Desktop.")
    from wingman import sandbox

    sandbox.ensure_image()
    return "daemon running, sandbox image ready"


def check_calendar() -> str:
    from wingman.calendar_reader import external_meetings

    source = config.env("WINGMAN_CALENDAR", str(config.ROOT / "data/sample/calendar.ics"))
    meetings = external_meetings(source)
    kind = "live feed" if source.startswith("https://") else "local file"
    if not meetings and not source.startswith("https://"):
        # The bundled sample has fixed dates and expires overnight, which makes
        # `brief --next` find nothing the next morning.
        raise Skip(f"{kind}: no upcoming meetings — run: wingman refresh-sample")
    return f"{kind}: {len(meetings)} upcoming external meetings"


def check_brain() -> str:
    if not (config.COGNEE_CLOUD_URL and config.COGNEE_API_KEY) and not config.env("LLM_API_KEY"):
        raise Skip("set COGNEE_CLOUD_URL + COGNEE_API_KEY (cloud), or LLM_API_KEY + "
                   "LLM_PROVIDER/EMBEDDING_PROVIDER for local graph building")
    from wingman import brain

    mode = brain.connect()
    try:
        answer = brain.recall("Who is the user meeting next?")
    except Exception as exc:
        # Cognee 404s with DatasetNotFoundError until something has been stored.
        # Connected-but-empty is a normal first-run state, so say what to do next.
        if "DatasetNotFoundError" in str(exc) or "No datasets found" in str(exc):
            raise Skip(f"{mode} mode, connected, but the brain is empty "
                       f"— run: wingman ingest data/sample") from exc
        raise
    return f"{mode} mode, recall returned {len(answer)} chars"


def check_web() -> str:
    if not config.BRIGHT_DATA_TOKEN:
        raise Skip("set API_TOKEN (Bright Data)")
    if not shutil.which("npx"):
        raise RuntimeError("npx not found. Install Node.js 18+.")
    from wingman.agent import _mcp_text, bright_data_client

    with bright_data_client() as web:
        tools = [t.tool_name for t in web.list_tools_sync()]
        result = web.call_tool_sync(uuid.uuid4().hex, "search_engine", {"query": "Cognee AI memory news"})
    return f"{len(tools)} tools, live search returned {len(_mcp_text(result))} chars"


def check_model() -> str:
    from wingman.agent import build_chain

    try:
        chain = build_chain()
    except config.MissingConfig as why:
        raise Skip(str(why)) from why
    from strands import Agent

    from wingman.agent import build_model

    model = build_model()
    reply = Agent(model=model, callback_handler=None)("Reply with the single word: ready")
    # `model.label` is whichever link in the chain actually answered, which is
    # the useful fact when an earlier one is out of quota.
    others = len(chain) - 1
    spare = f", {others} fallback{'s' if others != 1 else ''} ready" if others else ", no fallback"
    return f"{model.label} replied: {str(reply).strip()[:30]}{spare}"


def check_email() -> str:
    if not (config.SMTP_USER and config.SMTP_APP_PASSWORD):
        raise Skip("set SMTP_USER + SMTP_APP_PASSWORD (briefs are saved as .eml files until then)")
    with smtplib.SMTP_SSL(config.SMTP_HOST, 465, timeout=20) as smtp:
        smtp.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
    return f"SMTP login ok as {config.SMTP_USER}"


CHECKS: list[tuple[str, Callable[[], str]]] = [
    ("Docker sandbox", check_docker),
    ("Calendar", check_calendar),
    ("Cognee brain", check_brain),
    ("Bright Data web", check_web),
    ("LLM", check_model),
    ("Email", check_email),
]


def status() -> list[dict]:
    """Run every check and return one row each, without printing.

    Example row: {"name": "Bright Data web", "state": "pass",
                  "detail": "5 tools, live search returned 8421 chars"}
    """
    rows = []
    for name, check in CHECKS:
        try:
            rows.append({"name": name, "state": "pass", "detail": check()})
        except Skip as why:
            rows.append({"name": name, "state": "skip", "detail": str(why)})
        except Exception as exc:
            rows.append({"name": name, "state": "fail", "detail": str(exc)[:200]})
    return rows


def run() -> bool:
    """Print one row per check. Returns True if nothing outright failed.

    Example output row:  PASS  Bright Data web   5 tools, live search returned 8421 chars
    """
    colour = {"pass": GREEN, "skip": YELLOW, "fail": RED}
    rows = status()
    for row in rows:
        label = row["state"].upper()
        print(f"{colour[row['state']]}{label}{RESET}  {row['name']:<16} {row['detail']}")
    return not any(r["state"] == "fail" for r in rows)
