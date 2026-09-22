"use client";

import Link from "next/link";

import type { Health } from "@/lib/types";
import { BrainMark, Gear } from "./Icons";

interface Props {
  health: Health | null;
  healthError: string | null;
  busy: boolean;
  onBrief: () => void;
}

/** Glass bar over the workspace: identity, live readiness, and the one big action. */
export function TopBar({ health, healthError, busy, onBrief }: Props) {
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <header className="topbar glass">
      <div className="brand">
        <BrainMark />
        <span className="brand-name">Wingman</span>
        <span className="muted small" style={{ marginLeft: 4 }}>
          {today}
        </span>
      </div>

      <div className="topbar-right">
        <HealthPill health={health} error={healthError} />
        <Link href="/setup/" className="btn btn-sm" aria-label="Setup and health checks">
          <Gear size={17} />
          <span className="sr-only">Setup</span>
        </Link>
        <button
          type="button"
          className="btn btn-clay"
          onClick={onBrief}
          disabled={busy || !health?.ready}
          title={health?.ready ? "Brief the next meeting on your calendar" : "Finish setup first"}
        >
          {busy ? "Researching…" : "Brief next meeting"}
        </button>
      </div>
    </header>
  );
}

function HealthPill({ health, error }: { health: Health | null; error: string | null }) {
  if (error) {
    return (
      <span className="pill pill-bad" role="status">
        server unreachable
      </span>
    );
  }
  if (!health) {
    return (
      <span className="pill" role="status">
        checking…
      </span>
    );
  }

  const failing = health.checks.filter((c) => c.state === "fail").length;
  const missing = health.checks.filter((c) => c.state === "skip").length;

  if (health.ready && !failing) {
    return (
      <span className="pill pill-ok" role="status">
        <span className="dot" />
        ready
      </span>
    );
  }
  return (
    <Link
      href="/setup/"
      className={`pill ${failing ? "pill-bad" : "pill-warn"}`}
      role="status"
      style={{ textDecoration: "none" }}
    >
      {failing ? `${failing} failing` : `${missing} to configure`}
    </Link>
  );
}
