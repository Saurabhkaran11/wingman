"use client";

/** Live agent run: start one, then watch its Server-Sent Events. */

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "./api";
import type { RunEvent, RunSummary } from "./types";

export interface RunState {
  id: string | null;
  events: RunEvent[];
  status: "idle" | "running" | "done" | "error" | "disconnected";
  summary: RunSummary | null;
  seconds: number | null;
}

const IDLE: RunState = { id: null, events: [], status: "idle", summary: null, seconds: null };

export function useRun(onFinished?: (summary: RunSummary) => void) {
  const [run, setRun] = useState<RunState>(IDLE);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  // Held in a ref so `watch` never has to change identity when the callback does.
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;

  const closeStream = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  /** Attach to a run id. `seed` pre-fills events when rejoining a run in progress. */
  const watch = useCallback(
    (id: string, seed: RunEvent[] = []) => {
      closeStream();
      setRun({ id, events: seed, status: "running", summary: null, seconds: null });

      const source = new EventSource(api.streamUrl(id));
      sourceRef.current = source;

      source.onmessage = (message) => {
        const event = JSON.parse(message.data) as RunEvent;
        // The stream replays history on connect, so drop anything already held.
        setRun((prev) =>
          prev.events.some((e) => e.seq === event.seq)
            ? prev
            : { ...prev, events: [...prev.events, event] },
        );
      };

      source.addEventListener("done", (message) => {
        const summary = JSON.parse((message as MessageEvent).data) as RunSummary;
        closeStream();
        setRun({
          id,
          events: summary.events,
          status: summary.state === "error" ? "error" : "done",
          summary,
          seconds: summary.seconds,
        });
        finishedRef.current?.(summary);
      });

      source.onerror = () => {
        // EventSource reconnects by itself; only report a genuinely closed stream.
        if (source.readyState === EventSource.CLOSED) {
          setRun((prev) => ({ ...prev, status: "disconnected" }));
          setError("Lost the connection to the run.");
        }
      };
    },
    [closeStream],
  );

  const start = useCallback(
    async (body: { person?: string; company?: string; writeback?: boolean }) => {
      setError(null);
      try {
        const { run: id } = await api.startBrief(body);
        watch(id);
        return true;
      } catch (caught) {
        const message =
          caught instanceof ApiError && caught.status === 409
            ? "A brief is already running. Wait for it to finish."
            : caught instanceof Error
              ? caught.message
              : "Could not start the brief.";
        setError(message);
        return false;
      }
    },
    [watch],
  );

  /** On mount, rejoin a run that is already going (after a reload, or another tab). */
  useEffect(() => {
    let cancelled = false;
    api
      .activeRun()
      .then(({ run: active }) => {
        if (!cancelled && active) watch(active.id, active.events);
      })
      .catch(() => {
        /* the health check already reports an unreachable server */
      });
    return () => {
      cancelled = true;
      closeStream();
    };
  }, [watch, closeStream]);

  return { run, error, start, clearError: () => setError(null) };
}

/** Page reads used so far, for the spend meter. Derived, never counted twice. */
export function scrapeCount(events: RunEvent[]): number {
  return events.filter((e) => e.kind === "tool" && e.text.includes("read_web_page")).length;
}
