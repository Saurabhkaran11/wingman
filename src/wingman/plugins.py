"""The three Strands patterns from AWS's "Agent with a Brain" starter, adapted to Wingman.

  MEMORY    CogneeMemory     the Personal Brain as a Strands memory store, so relevant
                             memories are recalled and injected BEFORE every model call
  HOOK      AuditHook        deterministic code after every tool call: prints a line
                             and appends to out/run_<timestamp>.jsonl
  STEERING  ResearchPolicy   Python rules that run BEFORE a tool call and can block it:
                             caps on searches/scrapes, and drafts only to the attendee

None of these involve an LLM decision, which is the point: the demo's reliability and
cost do not depend on the model remembering the rules in its prompt.
"""

import json
import time
from datetime import datetime
from pathlib import Path

from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry
from strands.memory.types import MemoryEntry
from strands.vended_plugins.steering import Guide, Proceed, SteeringHandler

from wingman import brain, config


# ── MEMORY ──────────────────────────────────────────────────────────────────────────

class CogneeMemory:
    """Adapts brain.recall/remember to the Strands MemoryStore protocol.

    Strands' MemoryManager calls `search` with the latest message before each model
    call and prepends the results to the prompt. It also exposes `search` to the model
    as a tool (named recall_memory in agent.py) for explicit, targeted questions.
    """

    name = "personal_brain"
    description = "The user's emails, meeting notes, commitments and past interactions."
    max_search_results = 5
    writable = False      # write-back is deterministic code in cli.py, not an agent choice
    extraction = None

    async def search(self, query: str, options=None) -> list[MemoryEntry]:
        # Example: search("Priya Shah Cognee") -> [MemoryEntry(content="Priya leads DevRel..."), ...]
        limit = (options or {}).get("max_search_results", self.max_search_results)
        texts = await brain.recall_async(query, top_k=limit)
        return [MemoryEntry(content=t, store_name=self.name) for t in texts]

    async def add(self, content: str, metadata=None) -> None:
        await brain.remember_async(content)


def format_injection(ctx) -> str:
    # Renders recalled entries into the prompt. Wrapped in a tag so the system prompt can
    # say "facts in <personal_brain> come from the user's own notes".
    # Example: 3 entries -> "   [memory] 3 entries injected" on stderr, and
    #          "<personal_brain>\n...\n</personal_brain>" in the prompt.
    n = len(ctx.entries)
    print(f"   [memory] {n} entr{'y' if n == 1 else 'ies'} injected into the prompt")
    return "<personal_brain>\n" + "\n".join(e.content for e in ctx.entries) + "\n</personal_brain>"


# ── HOOK ────────────────────────────────────────────────────────────────────────────

class AuditHook(HookProvider):
    """Logs every tool call: one printed line for demo narration, one JSON line on disk.

    Example line in out/run_20260921-170102.jsonl:
      {"t": "2026-09-21T17:01:09", "tool": "web_search", "args": {"query": "\\"Priya Shah\\" \\"Cognee\\""},
       "status": "success", "ms": 1840, "result_chars": 8421}
    """

    def __init__(self, log_path: Path | None = None):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_path = log_path or config.OUT_DIR / f"run_{stamp}.jsonl"
        self.calls = 0

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self.after_tool)

    def after_tool(self, event: AfterToolCallEvent) -> None:
        self.calls += 1
        name = event.tool_use["name"]
        args = event.tool_use.get("input", {})
        status = event.result.get("status", "?") if event.result else "cancelled"
        chars = sum(len(c.get("text", "")) for c in (event.result or {}).get("content", []))
        ms = round((event.duration or 0) * 1000)
        preview = json.dumps(args)[:90]
        print(f"   [hook] #{self.calls} {name}({preview}) -> {status} in {ms} ms")
        with self.log_path.open("a") as f:
            f.write(json.dumps({"t": datetime.now().isoformat(timespec="seconds"), "tool": name, "args": args,
                                "status": status, "ms": ms, "result_chars": chars}) + "\n")


# ── STEERING ────────────────────────────────────────────────────────────────────────

class ResearchPolicy(SteeringHandler):
    """Rules checked before each tool runs. A blocked call is returned to the model with
    the reason, so it can adjust; the tool itself never executes.

    Rules:
      1. At most MAX_SEARCHES web searches and MAX_SCRAPES page reads per run (cost cap).
      2. Every web search must mention the attendee's name or company (wrong-person guard).
      3. A follow-up draft may only be addressed to the attendee.

    Example: 4th read_web_page call -> Guide("You have used all 3 page reads...") and the
    model proceeds to write the dossier with what it has.
    """

    MAX_SEARCHES = 3
    MAX_SCRAPES = 3

    def __init__(self, person: str, company: str):
        super().__init__(context_providers=[])
        self.person, self.company = person, company
        self.searches = self.scrapes = 0
        # Tokens that must appear in a search: any name part of 3+ letters, or the company.
        # Example: "Priya Shah", "Cognee" -> {"priya", "shah", "cognee"}
        self.keywords = {w.lower() for w in person.split() if len(w) >= 3} | ({company.lower()} if company else set())

    async def steer_before_tool(self, *, agent, tool_use, **kwargs):
        name, args = tool_use["name"], tool_use.get("input", {})

        if name == "web_search":
            query = str(args.get("query", "")).lower()
            if not any(k in query for k in self.keywords):
                return self._block(f"web_search query must mention {self.person} or {self.company}. "
                                   f"Rewrite the query to include one of them.")
            if self.searches >= self.MAX_SEARCHES:
                return self._block(f"You have used all {self.MAX_SEARCHES} web searches for this run. "
                                   "Read the pages you already found, or write the dossier now.")
            self.searches += 1

        elif name == "read_web_page":
            if self.scrapes >= self.MAX_SCRAPES:
                return self._block(f"You have used all {self.MAX_SCRAPES} page reads for this run. "
                                   "Write the dossier with what you have.")
            self.scrapes += 1

        elif name == "save_followup_draft":
            target = str(args.get("person", "")).lower()
            if not any(k in target for k in self.keywords if k != self.company.lower()):
                return self._block(f"Follow-up drafts may only be addressed to {self.person}.")

        return Proceed(reason="ok")

    @staticmethod
    def _block(reason: str) -> Guide:
        print(f"   [steering] BLOCKED: {reason}")
        return Guide(reason=reason)
