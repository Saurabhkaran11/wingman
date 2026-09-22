"""Pull real email from Gmail over IMAP, read-only.

Uses the same Gmail app password as the SMTP sender, so there is no OAuth
flow to set up during a hackathon. The mailbox is opened read-only: Wingman
never marks, moves or deletes mail.
"""

import imaplib

from wingman import config
from wingman.ingest import eml_to_text

# Marketing and notification mail adds noise to the graph and burns credits.
DEFAULT_FILTER = "-category:promotions -category:social -category:updates -from:noreply -from:no-reply"


def fetch_emails(query: str, limit: int = 25) -> list[tuple[str, str]]:
    """Return (label, text) for the newest `limit` emails matching a Gmail search.

    Args:
        query: Any Gmail search string, exactly as you would type it in the Gmail search box.
        limit: Maximum number of messages, newest first.

    Example:
        fetch_emails("from:priya@acme.com OR to:priya@acme.com newer_than:180d", limit=10)
        -> [("gmail:48211", "TYPE: email\\nDATE: ...\\nFROM: ...\\n\\n<body>"), ...]
    """
    if not (config.SMTP_USER and config.SMTP_APP_PASSWORD):
        raise SystemExit("SMTP_USER and SMTP_APP_PASSWORD (a Gmail app password) are required in .env")

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        imap.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
        imap.select('"[Gmail]/All Mail"', readonly=True)
        # X-GM-RAW lets us use Gmail's own search syntax over IMAP.
        raw_query = f"{query} {DEFAULT_FILTER}".replace('"', '\\"')
        _, data = imap.search(None, "X-GM-RAW", f'"{raw_query}"')
        ids = data[0].split()[-limit:]  # IMAP returns oldest first; keep the newest `limit`
        emails = []
        for msg_id in reversed(ids):
            _, parts = imap.fetch(msg_id, "(RFC822)")
            text = eml_to_text(parts[0][1])
            # Long threads quote every earlier reply; cap the size per message.
            emails.append((f"gmail:{msg_id.decode()}", text[:6000]))
        return emails
    finally:
        imap.logout()
