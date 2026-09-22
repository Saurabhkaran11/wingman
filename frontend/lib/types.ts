/** Mirrors the Pydantic models in src/wingman/models.py and the web API's shapes. */

export type CheckState = "pass" | "skip" | "fail";

export interface HealthCheck {
  name: string;
  state: CheckState;
  detail: string;
}

export interface Health {
  checks: HealthCheck[];
  /** True when the three services a brief actually needs are all passing. */
  ready: boolean;
  user: string;
}

export interface Meeting {
  title: string;
  start: string;
  location: string;
  attendees: string[];
}

export interface WebFact {
  statement: string;
  source_url: string;
  as_of: string;
}

export interface StaleAlert {
  memory_says: string;
  web_says: string;
  source_url: string;
}

export interface TimelineEvent {
  date: string;
  kind: string;
  summary: string;
}

export interface Dossier {
  person: string;
  role: string;
  company: string;
  how_we_know_each_other: string;
  last_interaction: TimelineEvent;
  i_owe_them: string[];
  they_owe_me: string[];
  whats_new: WebFact[];
  stale_alerts: StaleAlert[];
  talking_points: string[];
  timeline: TimelineEvent[];
}

export interface SavedDossier {
  slug: string;
  person: string;
  role: string;
  company: string;
  updated: string;
  has_pdf: boolean;
  counts: {
    i_owe_them: number;
    they_owe_me: number;
    stale_alerts: number;
    whats_new: number;
  };
}

/** Event kinds the agent emits. Each has its own colour in the trace panel. */
export type EventKind = "step" | "memory" | "tool" | "steering" | "warn" | "result" | "error";

export interface RunEvent {
  seq: number;
  at: number;
  kind: EventKind;
  text: string;
  detail: string;
}

export interface RunSummary {
  id: string;
  title: string;
  state: "running" | "done" | "error";
  error: string | null;
  result: {
    slug?: string;
    person?: string;
    pdf?: string | null;
    email?: string;
    remembered?: number;
    stale_alerts?: number;
    i_owe_them?: number;
    whats_new?: number;
  };
  seconds: number;
  events: RunEvent[];
}
