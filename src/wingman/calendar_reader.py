"""Read an .ics calendar and find meetings with people who are not me."""

import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from icalendar import Calendar

from wingman import config
from wingman.models import Meeting


def _attendees(event) -> list[str]:
    # ATTENDEE can be missing, a single value, or a list. Normalise to a list of
    # "Name <email>" strings and drop myself.
    # Example: [alex@example.com, priya.shah@example.com] -> ["Priya Shah <priya.shah@example.com>"]
    raw = event.get("attendee", [])
    raw = raw if isinstance(raw, list) else [raw]
    people = []
    for a in raw:
        email = str(a).removeprefix("mailto:").removeprefix("MAILTO:")
        if email.lower() == config.ME_EMAIL.lower():
            continue
        name = a.params.get("CN", email)
        people.append(f"{name} <{email}>")
    return people


def read_ics(source: str) -> bytes:
    # `source` is a local .ics path or a live https feed.
    # Example (real-time): Google Calendar -> Settings -> "Secret address in iCal format"
    #   read_ics("https://calendar.google.com/calendar/ical/.../basic.ics") -> b"BEGIN:VCALENDAR..."
    if source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=20) as resp:
            return resp.read()
    return Path(source).read_bytes()


def external_meetings(source: str, after: datetime | None = None) -> list[Meeting]:
    """All future meetings that include at least one external attendee, soonest first.

    Example: external_meetings("data/sample/calendar.ics")
      -> [Meeting(title="Coffee with Priya Shah (Cognee)", ...), Meeting(title="Follow-up with Daniel ...")]
    The "Team standup" event is skipped because its only attendee is me.
    """
    after = after or datetime.now(timezone.utc)
    cal = Calendar.from_ical(read_ics(source))
    meetings = []
    for event in cal.walk("VEVENT"):
        start = event.decoded("dtstart")
        if not isinstance(start, datetime):  # all-day events are plain dates
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        people = _attendees(event)
        if start < after or not people:
            continue
        meetings.append(
            Meeting(
                title=str(event.get("summary", "")),
                start=start.isoformat(),
                location=str(event.get("location", "")),
                attendees=people,
            )
        )
    return sorted(meetings, key=lambda m: m.start)
