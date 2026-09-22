"""Load a folder of personal data into the brain."""

import time
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Callable

TEXT_SUFFIXES = {".md", ".txt"}


def eml_to_text(raw: bytes) -> str:
    # Flatten a raw RFC 822 email (an .eml file or an IMAP fetch) into the same "header block + body" shape as the sample
    # .md files. Explicit FROM/TO/DATE lines are what let the graph extractor
    # work out who promised what to whom.
    # Example: an .eml from alex to priya dated 12 Jun
    #   -> "TYPE: email\nDATE: Fri, 12 Jun 2026 ...\nFROM: alex@...\nTO: priya@...\nSUBJECT: ...\n\n<body>"
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    body = msg.get_body(preferencelist=("plain",))
    # Email bodies use \r\n line endings; normalise so the text matches the .md files.
    content = body.get_content().replace("\r\n", "\n") if body else ""
    return (
        "TYPE: email\n"
        f"DATE: {msg['date']}\n"
        f"FROM: {msg['from']}\n"
        f"TO: {msg['to']}\n"
        f"SUBJECT: {msg['subject']}\n\n"
        f"{content}"
    )


def load_documents(folder: Path) -> list[tuple[str, str]]:
    """Return (filename, text) for every ingestible file, oldest filename first.

    Example: load_documents(Path("data/sample"))
      -> [("2026-05-14_intro_to_priya.md", "TYPE: email\\nDATE: ..."), ...]
    README files are skipped: they describe the data, they are not the data.
    """
    docs = []
    for path in sorted(folder.rglob("*"), key=lambda p: p.name):
        if path.name.lower() == "readme.md" or not path.is_file():
            continue
        if path.suffix in TEXT_SUFFIXES:
            docs.append((path.name, path.read_text()))
        elif path.suffix == ".eml":
            docs.append((path.name, eml_to_text(path.read_bytes())))
    return docs


def ingest_folder(
    folder: Path,
    remember: Callable[[str], None],
    log: Callable[[str], None] = print,
    limit: int | None = None,
    delay: float = 0.0,
) -> int:
    """Send each document to the brain with one remember() call per file.

    One call per file keeps failures isolated: a bad document is reported and
    skipped instead of sinking the whole batch.

    Args:
        limit: Stop after this many documents. Useful to prove the pipeline on one
            file before committing to a long ingest.
        delay: Seconds to wait between documents. Free-tier model keys are rate
            limited per minute, and ingestion is the burstiest thing Wingman does.

    Example: ingest_folder(Path("data/sample"), brain.remember, limit=1) -> 1
    """
    docs = load_documents(folder)[: limit or None]
    stored = 0
    for i, (name, text) in enumerate(docs, 1):
        log(f"[{i}/{len(docs)}] remembering {name}")
        try:
            remember(text)
            stored += 1
        except Exception as exc:  # keep going; report at the end
            log(f"    failed: {exc}")
        if delay and i < len(docs):
            time.sleep(delay)
    return stored
