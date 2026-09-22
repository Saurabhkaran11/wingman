"use client";

import { useCallback, useEffect, useState } from "react";

import { DossierView } from "@/components/DossierView";
import { BrainMark } from "@/components/Icons";
import { companyFromTitle, MeetingRail } from "@/components/MeetingRail";
import { TopBar } from "@/components/TopBar";
import { TracePanel } from "@/components/TracePanel";
import { api } from "@/lib/api";
import type { Dossier, Health, Meeting, SavedDossier } from "@/lib/types";
import { useRun } from "@/lib/useRun";

export default function Dashboard() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingsSource, setMeetingsSource] = useState("");
  const [meetingsError, setMeetingsError] = useState<string | null>(null);

  const [saved, setSaved] = useState<SavedDossier[]>([]);
  const [slug, setSlug] = useState<string | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [toast, setToast] = useState<{ text: string; bad: boolean } | null>(null);

  const openDossier = useCallback(async (next: string) => {
    try {
      setDossier(await api.dossier(next));
      setSlug(next);
      // Deep-link without a route: static export cannot pre-render unknown slugs.
      window.history.replaceState(null, "", `?brief=${encodeURIComponent(next)}`);
    } catch (caught) {
      setToast({ text: caught instanceof Error ? caught.message : "Could not open that brief", bad: true });
    }
  }, []);

  const loadSaved = useCallback(
    async (select?: string) => {
      try {
        const { dossiers } = await api.dossiers();
        setSaved(dossiers);
        if (select) await openDossier(select);
      } catch {
        /* the health pill already reports an unreachable server */
      }
    },
    [openDossier],
  );

  const { run, error: runError, start, clearError } = useRun((summary) => {
    if (summary.state === "error") return;
    setToast({ text: `Brief ready for ${summary.result.person}. ${summary.result.email ?? ""}`, bad: false });
    void loadSaved(summary.result.slug);
  });

  const busy = run.status === "running";

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setHealthError(null);
    } catch (caught) {
      setHealthError(caught instanceof Error ? caught.message : "unreachable");
    }
  }, []);

  // First load: health, calendar, saved briefs, and whatever was deep-linked.
  useEffect(() => {
    void refreshHealth();

    void (async () => {
      try {
        const data = await api.meetings();
        setMeetings(data.meetings);
        setMeetingsSource(data.source);
      } catch (caught) {
        setMeetingsError(caught instanceof Error ? caught.message : "unavailable");
      }
    })();

    const wanted = new URLSearchParams(window.location.search).get("brief");
    void loadSaved(wanted ?? undefined);
  }, [refreshHealth, loadSaved]);

  // Surface run failures the same way as everything else.
  useEffect(() => {
    if (runError) {
      setToast({ text: runError, bad: true });
      clearError();
    }
  }, [runError, clearError]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 7000);
    return () => clearTimeout(timer);
  }, [toast]);

  return (
    <div className="shell">
      <TopBar
        health={health}
        healthError={healthError}
        busy={busy}
        onBrief={() => void start({})}
      />

      <main className="workspace">
        <MeetingRail
          meetings={meetings}
          meetingsSource={meetingsSource}
          meetingsError={meetingsError}
          saved={saved}
          activeSlug={slug}
          busy={busy}
          onBriefMeeting={(meeting) =>
            void start({
              person: (meeting.attendees[0] ?? "").split("<")[0].trim(),
              company: companyFromTitle(meeting.title),
            })
          }
          // Ad-hoc people are researched but never written into the personal brain.
          onBriefPerson={(person, company) => void start({ person, company, writeback: false })}
          onOpen={(next) => void openDossier(next)}
        />

        <section className="column column-pad" aria-label="Dossier">
          {dossier && slug ? (
            <DossierView
              dossier={dossier}
              slug={slug}
              busy={busy}
              onRerun={() => void start({ person: dossier.person, company: dossier.company })}
            />
          ) : (
            <div className="empty">
              <div className="empty-art">
                <BrainMark size={38} />
              </div>
              <h2>No brief open</h2>
              <p>
                Pick a meeting on the left, or research anyone by name. Wingman reads your memory,
                checks the live web, and writes you a one-page dossier.
              </p>
            </div>
          )}
        </section>

        <TracePanel run={run} />
      </main>

      {toast && (
        <div className={`toast glass-strong${toast.bad ? " toast-bad" : ""}`} role="status">
          {toast.text}
        </div>
      )}
    </div>
  );
}
