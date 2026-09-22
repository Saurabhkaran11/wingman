"""The structured objects Wingman passes between its stages."""

from pydantic import BaseModel, Field


class Meeting(BaseModel):
    """One calendar event with at least one attendee who is not me."""

    title: str
    start: str  # ISO datetime, e.g. "2026-09-22T17:00:00+00:00"
    location: str = ""
    attendees: list[str]  # external attendees only, e.g. ["Priya Shah <priya.shah@example.com>"]


class WebFact(BaseModel):
    statement: str = Field(description="One fresh public fact, e.g. 'Acme raised a $40M Series B'")
    source_url: str = Field(description="URL the fact came from. Required for every web fact.")
    as_of: str = Field(description="ISO date the page was published, or today's date if unknown")


class StaleAlert(BaseModel):
    memory_says: str = Field(description="What the user's memory claims, e.g. 'Priya is a PM at Stripe'")
    web_says: str = Field(description="What the web says now, e.g. 'Priya joined Ramp in Aug 2026'")
    source_url: str


class TimelineEvent(BaseModel):
    date: str = Field(description="ISO date, e.g. 2026-06-10")
    kind: str = Field(description="One of: email, meeting, note")
    summary: str = Field(description="Under 12 words")


class Dossier(BaseModel):
    """The one-page brief. The agent must return exactly this shape."""

    person: str
    role: str = Field(description="Their job title as best known")
    company: str
    how_we_know_each_other: str
    last_interaction: TimelineEvent
    i_owe_them: list[str] = Field(description="Open commitments the user made to this person")
    they_owe_me: list[str] = Field(description="Open commitments this person made to the user")
    whats_new: list[WebFact] = Field(description="Fresh public facts from the web, each with a source URL")
    stale_alerts: list[StaleAlert] = Field(description="Memory facts the web now contradicts")
    talking_points: list[str] = Field(description="Exactly three openers linking shared history to their news")
    timeline: list[TimelineEvent] = Field(description="Every known interaction, oldest first")


# Worked example (abridged):
#   Dossier(
#       person="Priya Shah", role="DevRel Lead", company="Cognee",
#       i_owe_them=["Graph vs vector benchmark (promised for 2026-06-19)"],
#       stale_alerts=[StaleAlert(memory_says="$1.5M pre-seed", web_says="$7.5M seed", source_url="https://...")],
#       ...
#   )
