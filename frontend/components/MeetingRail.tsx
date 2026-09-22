"use client";

import { useState } from "react";

import type { Meeting, SavedDossier } from "@/lib/types";

interface Props {
  meetings: Meeting[];
  meetingsSource: string;
  meetingsError: string | null;
  saved: SavedDossier[];
  activeSlug: string | null;
  busy: boolean;
  onBriefMeeting: (meeting: Meeting) => void;
  onBriefPerson: (person: string, company: string) => void;
  onOpen: (slug: string) => void;
}

/** "Priya Shah <p@x.com>" -> "Priya Shah" */
function displayName(attendee: string): string {
  return attendee.split("<")[0].trim();
}

/** "Coffee with Priya Shah (Cognee)" -> "Cognee" */
export function companyFromTitle(title: string): string {
  const match = /\(([^)]+)\)\s*$/.exec(title);
  return match ? match[1] : "";
}

function clockTime(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime())
    ? ""
    : when.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function dayLabel(iso: string): string {
  const when = new Date(iso);
  return Number.isNaN(when.getTime())
    ? ""
    : when.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

export function MeetingRail(props: Props) {
  const [person, setPerson] = useState("");
  const [company, setCompany] = useState("");

  return (
    <div className="column neu column-pad rail">
      <section className="rail-group">
        <h2 className="eyebrow">Upcoming · {props.meetingsSource || "…"}</h2>
        {props.meetingsError ? (
          <p className="muted small">Calendar unavailable: {props.meetingsError}</p>
        ) : props.meetings.length === 0 ? (
          <p className="muted small">No upcoming meetings with anyone outside your company.</p>
        ) : (
          <div className="rail-list">
            {props.meetings.map((meeting) => (
              <button
                key={`${meeting.start}-${meeting.title}`}
                type="button"
                className="card"
                disabled={props.busy}
                onClick={() => props.onBriefMeeting(meeting)}
              >
                <span className="card-top">
                  <span className="card-time">{clockTime(meeting.start)}</span>
                  <span className="card-name">{displayName(meeting.attendees[0] ?? "")}</span>
                </span>
                <span className="card-sub">
                  {dayLabel(meeting.start)} · {meeting.title}
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="rail-group">
        <h2 className="eyebrow">Brief anyone</h2>
        <form
          style={{ display: "flex", flexDirection: "column", gap: 9 }}
          onSubmit={(submit) => {
            submit.preventDefault();
            const name = person.trim();
            if (!name) return;
            props.onBriefPerson(name, company.trim());
          }}
        >
          <label className="sr-only" htmlFor="adhoc-person">
            Person&rsquo;s full name
          </label>
          <input
            id="adhoc-person"
            className="input"
            placeholder="Full name"
            value={person}
            maxLength={120}
            autoComplete="off"
            onChange={(change) => setPerson(change.target.value)}
          />
          <label className="sr-only" htmlFor="adhoc-company">
            Company
          </label>
          <input
            id="adhoc-company"
            className="input"
            placeholder="Company"
            value={company}
            maxLength={120}
            autoComplete="off"
            onChange={(change) => setCompany(change.target.value)}
          />
          <button type="submit" className="btn btn-block" disabled={props.busy || !person.trim()}>
            Research them
          </button>
        </form>
        <p className="muted small">
          Public, professional information only. Nothing is written into your brain for people who
          are not on your calendar.
        </p>
      </section>

      <section className="rail-group">
        <h2 className="eyebrow">Saved briefs</h2>
        {props.saved.length === 0 ? (
          <p className="muted small">Nothing yet. Your first brief will appear here.</p>
        ) : (
          <div className="rail-list">
            {props.saved.map((item) => (
              <button
                key={item.slug}
                type="button"
                className="card"
                aria-current={item.slug === props.activeSlug}
                onClick={() => props.onOpen(item.slug)}
              >
                <span className="card-top">
                  <span className="card-name">{item.person}</span>
                </span>
                <span className="card-sub">{item.company || item.role}</span>
                <span className="card-flags">
                  {item.counts.i_owe_them > 0 && (
                    <span className="flag flag-warn">{item.counts.i_owe_them} you owe</span>
                  )}
                  {item.counts.they_owe_me > 0 && (
                    <span className="flag flag-ok">{item.counts.they_owe_me} they owe</span>
                  )}
                  {item.counts.stale_alerts > 0 && (
                    <span className="flag flag-plain">{item.counts.stale_alerts} stale</span>
                  )}
                </span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
