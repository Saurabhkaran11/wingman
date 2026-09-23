"""Read an .ics calendar and find meetings with people who are not me."""

import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Calendar

from wingman import config
from wingman.models import Meeting

# The sample calendar is written with fixed dates, so it silently goes stale:
# the day after those dates, nothing is "upcoming" and `brief --next` finds no
# meeting. refresh_sample_calendar() rewrites it relative to today.
SAMPLE_CALENDAR = config.ROOT / "data" / "sample" / "calendar.ics"

_SAMPLE_EVENTS = [
    # (uid, summary, location, days ahead, UTC hour, minutes long, attendee name, attendee email)
    ("standup", "Team standup", "", 1, 16, 15, "", ""),
    ("priya-coffee", "Coffee with Priya Shah (Cognee)", "Sightglass Coffee, 270 7th St, San Francisco",
     1, 17, 45, "Priya Shah", "priya.shah@example.com"),
    ("daniel-screen", "Follow-up with Daniel Okafor (Northwind Robotics)", "",
     2, 18, 30, "Daniel Okafor", "daniel.okafor@example.com"),
]


def refresh_sample_calendar(path: Path | None = None) -> Path:
    """Rewrite the sample calendar so its meetings are tomorrow and the day after.

    Run this before a demo. Without it the sample data expires overnight and
    `wingman brief --next` reports no upcoming meetings.

    Example: refresh_sample_calendar() -> PosixPath('data/sample/calendar.ics')
    """
    path = path or SAMPLE_CALENDAR
    today = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//wingman//sample//EN"]

    for uid, summary, location, days, hour, minutes, name, email in _SAMPLE_EVENTS:
        start = (today + timedelta(days=days)).replace(hour=hour)
        end = start + timedelta(minutes=minutes)
        stamp = "%Y%m%dT%H%M%SZ"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}-{start:%Y%m%d}@example.com",
            f"DTSTART:{start:{stamp}}",
            f"DTEND:{end:{stamp}}",
            f"SUMMARY:{summary}",
        ]
        if location:
            lines.append(f"LOCATION:{location}")
        lines += [
            "ORGANIZER;CN=Alex Rivera:mailto:alex@example.com",
            "ATTENDEE;CN=Alex Rivera:mailto:alex@example.com",
        ]
        if email:
            lines.append(f"ATTENDEE;CN={name}:mailto:{email}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    path.write_text("\n".join(lines) + "\n")
    return path


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
