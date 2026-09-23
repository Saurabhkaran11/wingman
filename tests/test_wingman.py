"""Offline tests: everything that does not need an API key.

Run:  uv run pytest -q
The two Docker tests are skipped automatically when the daemon is not running.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from wingman import actions, config
from wingman.calendar_reader import external_meetings
from wingman.ingest import eml_to_text, load_documents
from wingman.models import Dossier

ROOT = config.ROOT
SAMPLE = ROOT / "data" / "sample"
DOSSIER = Dossier.model_validate_json((ROOT / "examples" / "sample_dossier.json").read_text())
docker_up = subprocess.run(["docker", "info"], capture_output=True).returncode == 0


# --- calendar -------------------------------------------------------------

def test_calendar_skips_meetings_with_only_me(monkeypatch, tmp_path):
    # data/sample is the "Alex Rivera" persona; the test must not depend on
    # whichever address the developer happens to have in .env.
    monkeypatch.setattr(config, "ME_EMAIL", "alex@example.com")
    # Write the sample fresh into tmp: its dates are relative to today, so
    # reading the committed file would make this test depend on the clock.
    from wingman.calendar_reader import refresh_sample_calendar

    ics = refresh_sample_calendar(tmp_path / "calendar.ics")
    meetings = external_meetings(str(ics))
    titles = [m.title for m in meetings]
    assert "Team standup" not in titles
    assert titles[0] == "Coffee with Priya Shah (Cognee)"       # soonest first
    assert meetings[0].attendees == ["Priya Shah <priya.shah@example.com>"]


# --- ingestion ------------------------------------------------------------

def test_load_documents_skips_readme_and_calendar():
    names = [n for n, _ in load_documents(SAMPLE)]
    assert len(names) == 7
    assert "README.md" not in names and "calendar.ics" not in names


def test_eml_to_text_flattens_headers():
    raw = (b"From: Priya <priya@example.com>\r\nTo: alex@example.com\r\nDate: Fri, 12 Jun 2026 10:00:00 -0700\r\n"
           b"Subject: Benchmark\r\nContent-Type: text/plain\r\n\r\nI'll send it Friday.\r\n")
    text = eml_to_text(raw)
    assert text.startswith("TYPE: email\nDATE: Fri, 12 Jun 2026")
    assert "FROM: Priya <priya@example.com>" in text
    assert text.endswith("I'll send it Friday.\n")


# --- dossier + actions ----------------------------------------------------

def test_dossier_schema_rejects_web_fact_without_source():
    bad = json.loads(DOSSIER.model_dump_json())
    del bad["whats_new"][0]["source_url"]
    with pytest.raises(Exception):
        Dossier.model_validate(bad)


def test_markdown_contains_every_section():
    md = actions.to_markdown(DOSSIER)
    for heading in ("## You owe them", "## They owe you", "## What changed", "## Stale memory alerts", "## Talking points"):
        assert heading in md
    assert "https://www.cognee.ai/" in md                        # source URL survives


def test_email_without_smtp_is_saved_not_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)
    monkeypatch.setattr(config, "SMTP_USER", "")
    status = actions.send_dossier_email(DOSSIER, "Coffee with Priya", None)
    assert "saved email" in status and (tmp_path / "dossier_priya_shah.eml").exists()


def test_email_recipient_is_always_me(monkeypatch):
    # Even a dossier full of other people's addresses must only go to the user.
    monkeypatch.setattr(config, "SMTP_USER", "me@example.com")
    monkeypatch.setattr(config, "SMTP_APP_PASSWORD", "x")
    with mock.patch("smtplib.SMTP_SSL") as smtp:
        actions.send_dossier_email(DOSSIER, "Coffee", None)
    msg = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert msg["To"] == "me@example.com"


def test_followup_is_a_draft(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)
    path = actions.save_followup_draft("Priya Shah", "Benchmark", "Hi Priya")
    assert path.read_text().startswith("DRAFT - not sent")


# --- sandbox --------------------------------------------------------------

@pytest.mark.skipif(not docker_up, reason="Docker daemon not running")
def test_sandbox_renders_pdf():
    from wingman import sandbox
    pdf = sandbox.run_in_sandbox(DOSSIER.model_dump())
    assert pdf.read_bytes()[:4] == b"%PDF"
    assert (pdf.parent / "timeline.png").exists()
    sandbox.collect(pdf, pdf.parent.parent.parent / "test_dossier.pdf").unlink()


@pytest.mark.skipif(not docker_up, reason="Docker daemon not running")
def test_sandbox_has_no_network():
    from wingman import sandbox
    probe = ("import socket, pathlib\n"
             "try:\n    socket.create_connection(('1.1.1.1', 443), timeout=3); r='reachable'\n"
             "except OSError: r='blocked'\n"
             "pathlib.Path('/work/out/dossier.pdf').write_text(r)\n")
    pdf = sandbox.run_in_sandbox({}, script=probe)
    assert pdf.read_text() == "blocked"


# --- the whole brief pipeline, with only the key-gated parts mocked ---------

@pytest.mark.skipif(not docker_up, reason="Docker daemon not running")
def test_brief_pipeline_end_to_end(tmp_path, monkeypatch):
    from wingman import brain, cli
    monkeypatch.setattr(config, "OUT_DIR", tmp_path)
    monkeypatch.setattr(config, "SMTP_USER", "")
    remembered = []
    with mock.patch.object(brain, "connect", return_value="mock"), \
         mock.patch.object(brain, "remember", side_effect=remembered.append), \
         mock.patch("wingman.agent.bright_data_client", return_value=mock.MagicMock()), \
         mock.patch("wingman.agent.prepare_dossier", return_value=DOSSIER):
        monkeypatch.setattr(sys, "argv", ["wingman", "brief", "--next"])
        cli.main()
    assert (tmp_path / "dossier_priya_shah.pdf").exists()
    assert (tmp_path / "dossier_priya_shah.eml").exists()
    assert "These supersede older notes" in remembered[0]        # write-back happened


# --- the three Strands patterns (memory injection, hook, steering) ----------

def test_memory_store_adapts_brain_to_strands():
    import asyncio
    from wingman import brain
    from wingman.plugins import CogneeMemory

    async def fake(q, top_k=5):
        return ["Priya leads DevRel at Cognee", "You owe her a benchmark"]

    with mock.patch.object(brain, "recall_async", fake):
        entries = asyncio.run(CogneeMemory().search("Priya Shah"))
    assert [e.content for e in entries][0].startswith("Priya leads")
    assert entries[0].store_name == "personal_brain"


def test_memory_store_is_not_writable():
    # Write-back is deterministic code in cli.py; the agent must not decide it.
    from wingman.plugins import CogneeMemory

    assert CogneeMemory.writable is False


def test_audit_hook_writes_one_json_line_per_tool_call(tmp_path):
    from wingman.plugins import AuditHook

    log = tmp_path / "run.jsonl"
    hook = AuditHook(log_path=log)
    hook.after_tool(mock.Mock(tool_use={"name": "web_search", "input": {"query": "x"}},
                              result={"status": "success", "content": [{"text": "yz"}]}, duration=1.5))
    row = json.loads(log.read_text())
    assert (row["tool"], row["status"], row["ms"], row["result_chars"]) == ("web_search", "success", 1500, 2)


@pytest.mark.parametrize("name,args,expected", [
    ("web_search", {"query": "best pizza in SF"}, "guide"),        # off-topic query blocked
    ("web_search", {"query": '"Priya Shah" Cognee'}, "proceed"),
    ("read_web_page", {"url": "https://example.com"}, "proceed"),
    ("save_followup_draft", {"person": "Priya Shah"}, "proceed"),
    ("save_followup_draft", {"person": "Random Stranger"}, "guide"),  # wrong recipient blocked
])
def test_steering_rules(name, args, expected):
    import asyncio
    from wingman.plugins import ResearchPolicy

    policy = ResearchPolicy("Priya Shah", "Cognee")
    assert asyncio.run(policy.steer_before_tool(agent=None, tool_use={"name": name, "input": args})).type == expected


def test_steering_caps_searches_and_scrapes():
    import asyncio
    from wingman.plugins import ResearchPolicy

    policy = ResearchPolicy("Priya Shah", "Cognee")
    call = lambda n, a: asyncio.run(policy.steer_before_tool(agent=None, tool_use={"name": n, "input": a})).type
    # Read the caps off the policy: they are configurable, so hard-coding a
    # number here would just break again the next time they are tuned.
    searches, scrapes = policy.MAX_SEARCHES, policy.MAX_SCRAPES
    assert [call("web_search", {"query": "Cognee news"}) for _ in range(searches + 1)] == ["proceed"] * searches + ["guide"]
    assert [call("read_web_page", {"url": "https://x"}) for _ in range(scrapes + 1)] == ["proceed"] * scrapes + ["guide"]


def test_agent_exposes_recall_memory_from_the_memory_store():
    # MemoryManager builds recall_memory from CogneeMemory; build_tools must not duplicate it.
    from wingman import agent
    from wingman.models import Meeting

    meeting = Meeting(title="Coffee with Priya Shah (Cognee)", start="2026-09-22T17:00:00+00:00",
                      attendees=["Priya Shah <priya.shah@example.com>"])
    with mock.patch("wingman.agent.build_model", return_value=mock.MagicMock()):
        built = agent.build_agent(meeting, web=mock.MagicMock())
    assert sorted(built.tool_names) == ["read_web_page", "recall_memory", "save_followup_draft", "web_search"]


@pytest.mark.parametrize("attendee,expected", [
    ("Priya Shah <priya.shah@example.com>", ("Priya Shah", "")),
    ("Priya Shah (Cognee)", ("Priya Shah", "Cognee")),
])
def test_split_attendee(attendee, expected):
    from wingman.agent import split_attendee

    assert split_attendee(attendee) == expected


# --- the free-tier / fallback paths added late ------------------------------

def test_gemini_branch_constructs():
    # No key needed: this proves the provider wiring, not a live call.
    from wingman import config as cfg
    from wingman.agent import build_model

    blank = {k: "" for k in ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
                             "MODEL_ID", "MODEL_CHAIN")}
    with mock.patch.multiple(cfg, GEMINI_API_KEY="fake-key", **blank):
        model = build_model()
        # build_model now returns the whole chain behind one object.
        assert type(model).__name__ == "FallbackModel"
        assert model.label == "gemini/gemini-3.5-flash"
        assert model.get_config()["model_id"] == "gemini-3.5-flash"


@pytest.mark.parametrize("present,expected", [
    (["GEMINI_API_KEY", "ANTHROPIC_API_KEY"], "gemini"),   # card-free option wins
    (["ANTHROPIC_API_KEY"], "anthropic"),
    ([], "bedrock"),
])
def test_provider_resolution_prefers_the_card_free_option(present, expected, monkeypatch):
    """Resolution must come from the given env, never the developer's own .env."""
    import importlib

    from wingman import config as cfg

    # Set to empty rather than delete: reloading config calls load_dotenv(), which
    # would re-read the developer's real .env for any name that is absent. An
    # empty value is already present, so dotenv leaves it alone, and config
    # strips empties before resolving.
    for name in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "WINGMAN_MODEL_PROVIDER"):
        monkeypatch.setenv(name, "")
    for name in present:
        monkeypatch.setenv(name, "x")
    try:
        assert importlib.reload(cfg).MODEL_PROVIDER == expected
    finally:
        monkeypatch.undo()
        importlib.reload(cfg)   # restore the real config for every later test


def test_ingest_limit_and_delay():
    from wingman.ingest import ingest_folder

    stored = []
    assert ingest_folder(ROOT / "data/sample", stored.append, log=lambda _m: None, limit=2) == 2
    assert ingest_folder(ROOT / "data/sample", stored.append, log=lambda _m: None, limit=1, delay=0.01) == 1


def test_json_fallback_parses_a_fenced_reply():
    # What a model returns when it cannot satisfy the nested tool schema.
    from wingman.agent import _dossier_from_text

    fenced = "Sure, here you go:\n```json\n" + DOSSIER.model_dump_json() + "\n```"
    assert _dossier_from_text(fenced).person == "Priya Shah"


def test_json_fallback_rejects_a_reply_with_no_json():
    from wingman.agent import _dossier_from_text

    with pytest.raises(ValueError):
        _dossier_from_text("I could not complete the research.")


# --- the fallback chain and the web cache ----------------------------------

class _Dead:
    """A model that always fails with the given message."""

    def __init__(self, message):
        self.message = message

    async def stream(self, *a, **k):
        raise RuntimeError(self.message)
        yield  # pragma: no cover - unreachable, makes this an async generator

    async def structured_output(self, *a, **k):
        raise RuntimeError(self.message)
        yield  # pragma: no cover

    def get_config(self):
        return {"id": "dead"}

    def update_config(self, **kw):
        pass


class _Alive:
    def __init__(self):
        self.calls = 0

    async def stream(self, *a, **k):
        self.calls += 1
        yield {"event": "ok"}

    async def structured_output(self, *a, **k):
        yield {"output": "ok"}

    def get_config(self):
        return {"id": "alive"}

    def update_config(self, **kw):
        pass


@pytest.mark.parametrize("message,expected", [
    ("429 RESOURCE_EXHAUSTED quota exceeded", True),
    ("503 Service Unavailable: high demand", True),
    ("Rate limit reached for model", True),
    ("TypeError: bad schema", False),
])
def test_quota_error_detection(message, expected):
    from wingman.fallback import is_quota_error

    assert is_quota_error(RuntimeError(message)) is expected


def test_chain_fails_over_on_quota_and_retires_the_dead_model():
    import asyncio

    from wingman.fallback import FallbackModel

    alive = _Alive()
    model = FallbackModel([
        ("dead/quota", lambda: _Dead("429 RESOURCE_EXHAUSTED")),
        ("alive/good", lambda: alive),
    ])

    async def drain():
        return [e async for e in model.stream([])]

    assert asyncio.run(drain()) == [{"event": "ok"}]
    assert model.label == "alive/good"          # advanced past the dead one
    asyncio.run(drain())
    assert alive.calls == 2                     # dead model never retried


def test_chain_does_not_swallow_a_real_bug():
    import asyncio

    from wingman.fallback import FallbackModel

    model = FallbackModel([("dead/bug", lambda: _Dead("TypeError: bad schema")), ("alive", _Alive)])
    with pytest.raises(RuntimeError, match="bad schema"):
        asyncio.run(anext(model.stream([]).__aiter__()))


def test_exhausted_chain_names_the_fix():
    import asyncio

    from wingman.fallback import FallbackModel

    model = FallbackModel([("a", lambda: _Dead("429 quota")), ("b", lambda: _Dead("429 quota"))])

    async def drain():
        return [e async for e in model.stream([])]

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        asyncio.run(drain())


@pytest.mark.parametrize("keys,expected_first", [
    ({"GROQ_API_KEY": "g", "GEMINI_API_KEY": "x"}, "groq/llama-3.3-70b-versatile"),
    ({"GEMINI_API_KEY": "x"}, "gemini/gemini-3.5-flash"),
    ({"ANTHROPIC_API_KEY": "a"}, "anthropic/claude-sonnet-5"),
])
def test_chain_orders_by_free_tier_generosity(keys, expected_first):
    from wingman import config as cfg
    from wingman.agent import build_chain

    blank = {k: "" for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
                             "OPENROUTER_API_KEY", "MODEL_ID", "MODEL_CHAIN")}
    with mock.patch.multiple(cfg, **{**blank, **keys}):
        chain = build_chain()
    assert chain[0][0] == expected_first
    assert len(chain) >= 1


def test_no_keys_at_all_names_the_free_option():
    from wingman import config as cfg
    from wingman.agent import build_chain

    blank = {k: "" for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
                             "OPENROUTER_API_KEY", "MODEL_ID", "MODEL_CHAIN")}
    with mock.patch.multiple(cfg, **blank), \
         mock.patch.object(cfg, "env", return_value=""):
        with pytest.raises(cfg.MissingConfig, match="GROQ_API_KEY"):
            build_chain()


def test_web_cache_round_trip(tmp_path, monkeypatch):
    from wingman import webcache

    monkeypatch.setattr(webcache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "WEB_CACHE_HOURS", 12)

    assert webcache.get("search_engine", {"query": "Cognee"}) is None
    webcache.put("search_engine", {"query": "Cognee"}, "results here")
    assert webcache.get("search_engine", {"query": "Cognee"}) == "results here"
    # A different query is a different key.
    assert webcache.get("search_engine", {"query": "something else"}) is None


def test_web_cache_expires_and_can_be_disabled(tmp_path, monkeypatch):
    import json
    import time

    from wingman import webcache

    monkeypatch.setattr(webcache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "WEB_CACHE_HOURS", 12)
    webcache.put("search_engine", {"query": "x"}, "old")

    # Age the entry past the window.
    path = next(tmp_path.glob("*.json"))
    entry = json.loads(path.read_text())
    entry["at"] = time.time() - 13 * 3600
    path.write_text(json.dumps(entry))
    assert webcache.get("search_engine", {"query": "x"}) is None

    monkeypatch.setattr(config, "WEB_CACHE_HOURS", 0)
    webcache.put("search_engine", {"query": "y"}, "ignored")
    assert webcache.get("search_engine", {"query": "y"}) is None


def test_corrupt_cache_file_is_a_miss_not_a_crash(tmp_path, monkeypatch):
    from wingman import webcache

    monkeypatch.setattr(webcache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "WEB_CACHE_HOURS", 12)
    webcache.put("search_engine", {"query": "x"}, "fine")
    next(tmp_path.glob("*.json")).write_text("{truncated")
    assert webcache.get("search_engine", {"query": "x"}) is None
