"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ArrowLeft, BrainMark, Check } from "@/components/Icons";
import { api } from "@/lib/api";
import type { CheckState, Health } from "@/lib/types";

/** What each check needs, so the page can say more than "SKIP". */
const GUIDE: Record<string, { env: string[]; note: string }> = {
  "Docker sandbox": {
    env: [],
    note: "Start Docker Desktop. The sandbox image builds itself on first use.",
  },
  Calendar: {
    env: ["WINGMAN_CALENDAR", "WINGMAN_ME"],
    note: "Leave blank to use the bundled sample calendar. For your own, paste the secret iCal URL from Google Calendar → Settings → your calendar.",
  },
  "Cognee brain": {
    env: ["COGNEE_CLOUD_URL", "COGNEE_API_KEY"],
    note: "From the Cognee Cloud console. Or set LLM_API_KEY instead to build the graph locally.",
  },
  "Bright Data web": {
    env: ["API_TOKEN"],
    note: "Your Bright Data API token. The MCP server reads this exact variable name.",
  },
  LLM: {
    env: ["ANTHROPIC_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    note: "Either an Anthropic key, or AWS credentials with Bedrock access. One is enough.",
  },
  Email: {
    env: ["SMTP_USER", "SMTP_APP_PASSWORD"],
    note: "Optional. A Gmail app password. Without it, briefs are saved as .eml files instead of sent.",
  },
};

const TINT: Record<CheckState, string> = {
  pass: "flag flag-ok",
  skip: "flag flag-warn",
  fail: "flag flag-warn",
};

export default function SetupPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  const check = useCallback(async () => {
    setChecking(true);
    try {
      setHealth(await api.health());
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "unreachable");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  const passing = health?.checks.filter((c) => c.state === "pass").length ?? 0;
  const total = health?.checks.length ?? 0;

  return (
    <div className="shell" style={{ height: "auto", overflow: "visible" }}>
      <header className="topbar glass">
        <div className="brand">
          <BrainMark />
          <span className="brand-name">Wingman</span>
          <span className="muted small" style={{ marginLeft: 4 }}>
            Setup
          </span>
        </div>
        <div className="topbar-right">
          <button type="button" className="btn btn-sm" onClick={() => void check()} disabled={checking}>
            {checking ? "Checking…" : "Re-check"}
          </button>
          <Link href="/" className="btn btn-sm btn-clay">
            <ArrowLeft size={16} />
            Dashboard
          </Link>
        </div>
      </header>

      <main style={{ padding: 14, maxWidth: 820, width: "100%", margin: "0 auto" }}>
        <section className="column neu column-pad" style={{ padding: 32 }}>
          <h1 style={{ fontSize: 28, marginBottom: 10 }}>
            {health?.ready ? "Wingman is ready" : "Finish setting up Wingman"}
          </h1>
          <p className="muted" style={{ lineHeight: 1.65, margin: "0 0 8px", maxWidth: 620 }}>
            Every row below makes one small real call, so a green row means that service works right
            now — not merely that a key is present. Edit <code>.env</code> in the project root, then
            re-check.
          </p>

          {health && (
            <p className="small muted" style={{ margin: "0 0 22px" }}>
              {passing} of {total} checks passing
              {health.ready ? " · briefs can run" : " · a brief needs Cognee, Bright Data and an LLM"}
            </p>
          )}

          {error && (
            <div className="panel panel-alert" style={{ marginBottom: 22 }}>
              <div className="panel-title">Cannot reach the server</div>
              <p className="alert-row" style={{ margin: 0 }}>
                {error} Start it with <code>uv run wingman web</code>.
              </p>
            </div>
          )}

          <ul className="checks">
            {health?.checks.map((item) => {
              const guide = GUIDE[item.name];
              return (
                <li className="check" key={item.name}>
                  <span className={`check-state ${TINT[item.state]}`}>{item.state.toUpperCase()}</span>
                  <span style={{ minWidth: 0 }}>
                    <span className="check-name">{item.name}</span>
                    <span className="check-detail">{item.detail}</span>
                    {item.state !== "pass" && guide && (
                      <span className="check-detail" style={{ marginTop: 6 }}>
                        {guide.env.length > 0 && (
                          <>
                            {guide.env.map((name) => (
                              <code key={name} style={{ marginRight: 6 }}>
                                {name}
                              </code>
                            ))}
                            <br />
                          </>
                        )}
                        {guide.note}
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>

          {health?.ready && (
            <div className="panel" style={{ marginTop: 24, display: "flex", gap: 13, alignItems: "flex-start" }}>
              <span style={{ color: "var(--green-ink)", flexShrink: 0, marginTop: 2 }}>
                <Check size={18} />
              </span>
              <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6 }}>
                Everything a brief needs is live. Build your brain first with{" "}
                <code>uv run wingman ingest data/sample</code>, then head back to the dashboard.
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
