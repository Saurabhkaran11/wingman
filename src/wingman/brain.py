"""Thin wrapper around Cognee — the Personal Brain.

Cognee is async and keeps loop-bound resources (DB engines, HTTP sessions).
Strands tools are sync and may run on different threads, so calling
asyncio.run() per tool call would create a new event loop each time and break
those resources. Instead we run ONE background event loop for the whole
process and submit every Cognee coroutine to it.
"""

import asyncio
import threading
from typing import Any, Coroutine

from wingman import config  # noqa: F401  (must run before cognee is imported)

import cognee  # noqa: E402

_loop = asyncio.new_event_loop()
threading.Thread(target=_loop.run_forever, name="cognee-loop", daemon=True).start()
_connected = False


def _run(coro: Coroutine[Any, Any, Any], timeout: float = 600) -> Any:
    # Submit a coroutine to the shared loop and block until it finishes.
    # Example: _run(cognee.recall(query_text="hi")) -> list of recall entries
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout)


def _submit(coro: Coroutine[Any, Any, Any]) -> asyncio.Future:
    # Same, but returns an awaitable for callers that are themselves async on a
    # DIFFERENT loop (Strands' memory store). Awaiting it never blocks that loop.
    # Example: await _submit(cognee.recall(query_text="hi"))
    return asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, _loop))


def connect() -> str:
    """Connect once. Returns "cloud" or "local" so the CLI can say which."""
    global _connected
    if config.COGNEE_CLOUD_URL and config.COGNEE_API_KEY:
        if not _connected:
            # After serve(), remember/recall/forget all route to the cloud tenant,
            # so graph building uses Cognee credits instead of a local LLM key.
            _run(cognee.serve(url=config.COGNEE_CLOUD_URL, api_key=config.COGNEE_API_KEY))
            _connected = True
        return "cloud"
    # Local mode: Cognee needs LLM_API_KEY (and embedding config) in .env.
    return "local"


def remember(text: str) -> None:
    """Store one document or fact. Runs ingest -> chunk -> entities -> graph."""
    connect()
    _run(cognee.remember(text, dataset_name=config.DATASET))


def _texts(entries: list) -> list[str]:
    """Pull the readable text out of whatever recall returned.

    Cognee Cloud answers with plain dicts and the local SDK with objects, and
    either may carry the text under `text` (graph entries) or `answer` (QA
    entries). Reading only attributes silently dropped every cloud result.

    Example: [{"kind": "graph_completion", "text": "You promised ..."}]
             -> ["You promised ..."]
    """
    out = []
    for entry in entries:
        if isinstance(entry, dict):
            text = entry.get("text") or entry.get("answer")
        else:
            text = getattr(entry, "text", None) or getattr(entry, "answer", None)
        if text:
            out.append(str(text))
    return out


def recall(question: str) -> str:
    """Ask the brain a natural-language question and get text back."""
    connect()
    entries = _run(cognee.recall(query_text=question, datasets=[config.DATASET]))
    return "\n".join(_texts(entries)) or "Nothing in memory about that."


async def recall_async(question: str, top_k: int = 5) -> list[str]:
    """Async recall for Strands' memory store: one string per memory entry.

    Example: await recall_async("Priya Shah") -> ["Priya Shah leads DevRel at Cognee", ...]
    """
    connect()
    entries = await _submit(cognee.recall(query_text=question, datasets=[config.DATASET], top_k=top_k))
    return _texts(entries)


async def remember_async(text: str) -> None:
    """Async remember for Strands' memory store."""
    connect()
    await _submit(cognee.remember(text, dataset_name=config.DATASET))


def forget_everything() -> None:
    """Wipe this project's dataset so a demo can start from a clean brain."""
    connect()
    _run(cognee.forget(dataset=config.DATASET))


def visualize(path: str) -> str:
    """Write an interactive HTML view of the knowledge graph and return its path."""
    connect()
    return _run(cognee.visualize_graph(path, dataset=config.DATASET))


# Worked example:
#   remember("DATE: 2026-06-12\nFROM: Alex\nTO: Priya\n\nI'll send the benchmark by Friday June 19.")
#   recall("What did I promise Priya Shah?")
#   -> "You promised Priya Shah a graph-vs-vector benchmark by Friday June 19 (email of 2026-06-12)."
