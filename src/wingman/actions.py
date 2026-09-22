"""The things Wingman does with a finished dossier.

Guardrail: Wingman only ever SENDS mail to the user themself. Anything
addressed to another person is written to disk as a draft for the user to
review and send by hand.
"""

import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

from wingman import config
from wingman.models import Dossier


def slug(name: str) -> str:
    # File-safe version of a person's name.
    # Example: slug("Priya Shah") -> "priya_shah"
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def to_markdown(d: Dossier) -> str:
    """Plain-text version of the dossier: the email body and the no-Docker fallback."""

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items) or "- None found."

    parts = [
        f"# {d.person}",
        f"{d.role} at {d.company}",
        "",
        d.how_we_know_each_other,
        "",
        "## Last time",
        f"{d.last_interaction.date}: {d.last_interaction.summary}",
        "",
        "## You owe them",
        bullets(d.i_owe_them),
        "",
        "## They owe you",
        bullets(d.they_owe_me),
        "",
        "## What changed since you last spoke",
        bullets([f"{f.statement} ({f.source_url})" for f in d.whats_new]),
    ]
    if d.stale_alerts:
        parts += ["", "## Stale memory alerts"]
        parts += [f"- Your notes say: {a.memory_says}\n  The web says: {a.web_says} ({a.source_url})" for a in d.stale_alerts]
    parts += ["", "## Talking points", bullets(d.talking_points), ""]
    return "\n".join(parts)


def send_dossier_email(d: Dossier, meeting_title: str, pdf: Path | None) -> str:
    """Email the dossier to the user. Returns a one-line status for the CLI.

    If SMTP is not configured the message is saved as an .eml file instead, so
    the demo still has something to open.
    Example: send_dossier_email(dossier, "Coffee with Priya", Path("out/dossier_priya_shah.pdf"))
      -> "emailed dossier to alex@example.com"
    """
    # The recipient is never taken from the dossier or the agent: it is always me.
    recipient = config.SMTP_USER or config.ME_EMAIL

    msg = EmailMessage()
    msg["Subject"] = f"Wingman brief: {meeting_title}"
    msg["From"] = recipient
    msg["To"] = recipient
    msg.set_content(to_markdown(d))
    if pdf and pdf.exists():
        msg.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf", filename=pdf.name)

    if not (config.SMTP_USER and config.SMTP_APP_PASSWORD):
        path = config.OUT_DIR / f"dossier_{slug(d.person)}.eml"
        path.write_bytes(msg.as_bytes())
        return f"SMTP not configured; saved email to {config.show(path)}"

    with smtplib.SMTP_SSL(config.SMTP_HOST, 465, timeout=30) as smtp:
        smtp.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
        smtp.send_message(msg)
    return f"emailed dossier to {recipient}"


def save_followup_draft(person: str, subject: str, body: str) -> Path:
    """Write a follow-up message to disk as a draft. It is never sent.

    Example: save_followup_draft("Priya Shah", "The benchmark I owe you", "Hi Priya, ...")
      -> PosixPath("out/followup_priya_shah.md")
    """
    path = config.OUT_DIR / f"followup_{slug(person)}.md"
    path.write_text(f"DRAFT - not sent. Review before sending.\nTo: {person}\nSubject: {subject}\n\n{body}\n")
    return path
