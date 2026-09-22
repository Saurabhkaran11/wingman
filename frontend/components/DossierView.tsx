"use client";

import { api, safeUrl } from "@/lib/api";
import type { Dossier } from "@/lib/types";
import { Alert, Document } from "./Icons";

const TIMELINE_TINT: Record<string, string> = {
  meeting: "#35b37e",
  email: "#4c6fff",
  note: "#f2a03d",
};

/** A [source] chip, rendered only for a real http(s) URL. */
function Source({ url }: { url: string }) {
  const safe = safeUrl(url);
  if (!safe) return null;
  return (
    <a className="source" href={safe} target="_blank" rel="noopener noreferrer">
      [source]
    </a>
  );
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) {
    return (
      <p className="muted small" style={{ margin: 0 }}>
        Nothing outstanding.
      </p>
    );
  }
  return (
    <ul>
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

interface Props {
  dossier: Dossier;
  slug: string;
  busy: boolean;
  onRerun: () => void;
}

export function DossierView({ dossier, slug, busy, onRerun }: Props) {
  return (
    <article className="dossier">
      <header className="dossier-head">
        <div>
          <h1>{dossier.person}</h1>
          <div className="dossier-role">
            {dossier.role}
            {dossier.company ? ` at ${dossier.company}` : ""}
          </div>
          <p className="dossier-how">{dossier.how_we_know_each_other}</p>
        </div>
        <div className="dossier-actions">
          <a className="btn btn-sm" href={api.pdfUrl(slug)} target="_blank" rel="noopener noreferrer">
            <Document size={16} />
            PDF
          </a>
          <button type="button" className="btn btn-sm btn-clay" onClick={onRerun} disabled={busy}>
            {busy ? "Running…" : "Re-run"}
          </button>
        </div>
      </header>

      <section className="panel">
        <div className="panel-title">Last time</div>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6 }}>
          {dossier.last_interaction.date} — {dossier.last_interaction.summary}
        </p>
      </section>

      <div className="two-up">
        <section className="panel">
          <div className="panel-title">You owe them</div>
          <Bullets items={dossier.i_owe_them} />
        </section>
        <section className="panel">
          <div className="panel-title">They owe you</div>
          <Bullets items={dossier.they_owe_me} />
        </section>
      </div>

      {dossier.stale_alerts.length > 0 && (
        <section className="panel panel-alert">
          <div className="panel-title">
            <Alert />
            Stale memory — the web disagrees with your notes
          </div>
          {dossier.stale_alerts.map((alert, index) => (
            <div className="alert-row" key={index}>
              <strong>Your notes say:</strong> {alert.memory_says}
              <br />
              <strong>The web says:</strong> {alert.web_says}
              <Source url={alert.source_url} />
            </div>
          ))}
        </section>
      )}

      <section className="panel">
        <div className="panel-title">What changed since you last spoke</div>
        {dossier.whats_new.length === 0 ? (
          <p className="muted small" style={{ margin: 0 }}>
            No fresh public information found.
          </p>
        ) : (
          <ul>
            {dossier.whats_new.map((fact, index) => (
              <li key={index}>
                {fact.statement}
                <Source url={fact.source_url} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel panel-points">
        <div className="panel-title">Open with this</div>
        <Bullets items={dossier.talking_points} />
      </section>

      {dossier.timeline.length > 0 && (
        <section className="panel">
          <div className="panel-title">Timeline</div>
          <div className="timeline">
            {dossier.timeline.map((event, index) => (
              <div className="tl-row" key={index}>
                <span className="tl-date">{event.date}</span>
                <span
                  className="tl-mark"
                  style={{ background: TIMELINE_TINT[event.kind] ?? "#8c95ad" }}
                />
                <span className="tl-text">{event.summary}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
