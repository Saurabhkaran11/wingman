"use client";

import { useEffect, useRef } from "react";

import { scrapeCount, type RunState } from "@/lib/useRun";

const MAX_SCRAPES = 3; // mirrors ResearchPolicy.MAX_SCRAPES in src/wingman/plugins.py

const STATUS_PILL: Record<RunState["status"], string> = {
  idle: "pill",
  running: "pill pill-run",
  done: "pill pill-ok",
  error: "pill pill-bad",
  disconnected: "pill pill-warn",
};

/** Live narration of the agent: what it recalled, ran, and what got blocked. */
export function TracePanel({ run }: { run: RunState }) {
  const endRef = useRef<HTMLDivElement>(null);
  const count = scrapeCount(run.events);

  // Keep the newest event in view as the run streams in.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [run.events.length]);

  return (
    <div className="column neu column-pad" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <h2 className="eyebrow">
          Agent run{run.seconds !== null ? ` · ${run.seconds}s` : ""}
        </h2>
        <span className={STATUS_PILL[run.status]} role="status">
          {run.status === "running" && <span className="dot dot-live" />}
          {run.status}
        </span>
      </div>

      {run.events.length === 0 ? (
        <p className="muted small">
          Start a brief and every step appears here as it happens: what was recalled from your
          brain, which tools ran, and anything the steering policy blocked.
        </p>
      ) : (
        <div className="trace">
          {run.events.map((event) => (
            <div className="trace-row" key={event.seq}>
              <span className={`trace-dot k-${event.kind}-dot`} />
              <span style={{ minWidth: 0 }}>
                <span className={`trace-label k-${event.kind}`}>{event.text}</span>
                {event.detail && <span className="trace-detail">{event.detail}</span>}
              </span>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      )}

      {run.status === "error" && run.summary?.error && (
        <div className="panel panel-alert">
          <div className="panel-title">The run failed</div>
          <p className="alert-row" style={{ margin: 0 }}>
            {run.summary.error}
          </p>
        </div>
      )}

      <div className="meter" style={{ marginTop: "auto" }}>
        <div className="small muted">Bright Data this run</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
          <span className="meter-value">
            {Math.min(count, MAX_SCRAPES)} / {MAX_SCRAPES}
          </span>
          <span className="small muted">page reads · capped in code</span>
        </div>
        <div className="meter-track">
          <div
            className="meter-fill"
            style={{ width: `${Math.min(count / MAX_SCRAPES, 1) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
