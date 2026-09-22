# Wingman — Examples and Demo Guide

- Every command below is run from the project root.
- Outputs marked **verified** were produced on this machine on 2026-09-21.
- Outputs marked **expected** need your API keys, so they show the shape of the result, not a captured run.

---

## Example 1 — Check that everything is live (verified)

```bash
uv run wingman doctor
```

- Each row makes one small real call, so `PASS` means the service works right now.
- Output with no keys filled in yet:

```text
PASS  Docker sandbox   daemon running, sandbox image ready
PASS  Calendar         local file: 2 upcoming external meetings
SKIP  Cognee brain     set COGNEE_CLOUD_URL + COGNEE_API_KEY (cloud) or LLM_API_KEY (local)
SKIP  Bright Data web  set API_TOKEN (Bright Data)
SKIP  LLM              set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (Bedrock), or ANTHROPIC_API_KEY
SKIP  Email            set SMTP_USER + SMTP_APP_PASSWORD (briefs are saved as .eml files until then)
```

- Goal before the demo: six `PASS` rows.

## Example 2 — Find the meetings worth briefing (verified)

```bash
uv run wingman meetings
```

```text
2026-09-22T17:00:00+00:00  Coffee with Priya Shah (Cognee)  ->  Priya Shah <priya.shah@example.com>
2026-09-23T18:00:00+00:00  Follow-up with Daniel Okafor (Northwind Robotics)  ->  Daniel Okafor <daniel.okafor@example.com>
```

- The sample calendar has three events.
- "Team standup" is skipped because its only attendee is me.

## Example 3 — Render and send a dossier offline (verified)

```bash
uv run wingman render examples/sample_dossier.json
```

```text
==> Rendering PDF inside the Docker sandbox (no network)
wrote out/dossier_priya_shah.pdf

==> Sending the brief
SMTP not configured; saved email to out/dossier_priya_shah.eml
```

- This needs no API keys, so it is the Wi-Fi-is-down fallback for the demo.
- Open the result:

```bash
open out/dossier_priya_shah.pdf
```

## Example 4 — Prove the sandbox is locked down (verified)

```bash
docker run --rm --network none --read-only --tmpfs /tmp --cap-drop ALL wingman-sandbox python -c 'import socket; socket.create_connection(("1.1.1.1", 443), timeout=3)'
```

```text
OSError: [Errno 101] Network is unreachable
```

- The same flags are used for every render, plus memory, CPU and process limits.
- A write to `/etc` inside the container fails with `Read-only file system`.

## Example 4b — Run the offline test suite (verified)

```bash
uv run pytest -q
```

```text
.......................                                                  [100%]
23 passed in 14.24s
```

- Includes the memory store, the audit hook, and all five steering rules.

## Example 5 — Build the brain from the sample data (expected)

```bash
uv run wingman ingest data/sample
```

```text
==> Connecting to Cognee (cloud mode), dataset 'wingman'
[1/7] remembering 2026-05-14_intro_to_priya.md
[2/7] remembering 2026-05-20_priya_reply.md
...
remembered 7 documents
```

- Then ask the brain directly:

```bash
uv run wingman ask "What did I promise Priya Shah, and did I deliver it?"
```

- Expected answer: you promised a graph memory vs vector RAG benchmark by Friday June 19, and on June 25 Priya said she was still waiting for it.
- This answer needs three documents joined together (the call notes, your June 12 email, her June 25 email), which is the graph-memory point of the demo.

## Example 6 — The full run on live data (expected)

```bash
uv run wingman brief --next
```

```text
==> Next meeting: Coffee with Priya Shah (Cognee) with Priya Shah <priya.shah@example.com>
==> Connecting brain (cloud mode) and Bright Data
==> Agent is researching
   [memory] 5 entries injected into the prompt
   [hook] #1 recall_memory({"query": "commitments to Priya Shah"}) -> success in 2140 ms
   [memory] 5 entries injected into the prompt
   [hook] #2 web_search({"query": "\"Priya Shah\" \"Cognee\""}) -> success in 1840 ms
   [hook] #3 read_web_page({"url": "https://..."}) -> success in 2610 ms
   [steering] BLOCKED: You have used all 3 page reads for this run. Write the dossier with what you have.
   [hook] #6 save_followup_draft({"person": "Priya Shah"}) -> success in 3 ms
==> Rendering PDF inside the Docker sandbox (no network)
wrote out/dossier_priya_shah.pdf
==> Sending the brief
emailed dossier to you@gmail.com
==> Writing new facts back into the brain
remembered 3 new facts
==> Done in 74s
{"stale_alerts": 2, "i_owe_them": 2, "web_facts": 3}
```

- **What the seeded data should trigger:**
  - An open commitment: the benchmark promised for 2026-06-19.
  - A stale alert on funding: the notes say "$1.5M pre-seed"; the live web reports a later, larger round.
  - A stale alert on product: the notes say "no cloud offering"; the live web shows Cognee Cloud.
  - A follow-up draft in `out/followup_priya_shah.md` that owns the late benchmark.
- **What the three patterns add to the demo:**
  - `[memory]` lines prove Cognee is consulted before every step, not just when the model chooses to.
  - `[hook]` lines give a numbered, timed trace, also written to `out/run_<timestamp>.jsonl`.
  - A `[steering]` line is the moment to point out that the cap is Python, not a prompt.
- **Run it a second time:** the stale alerts should shrink, because the first run wrote the fresh facts back into the brain. That is the "brain that corrects itself" moment.

## Example 7 — Any real person, straight from the web (expected)

```bash
uv run wingman brief --person "Full Name" --company "Their Company" --no-writeback
```

- This is the live twist for the judges: no calendar entry needed.
- The brain has no history with them, so the dossier is built from live public data only.
- `--no-writeback` keeps a stranger's details out of your personal brain.
- Ask the person first, and keep it to public, professional information.

---

## Going from sample data to your real data

### Real email (live Gmail, read-only)

1. Create a Gmail app password at https://myaccount.google.com/apppasswords and put it in `.env` as `SMTP_APP_PASSWORD`, with your address as `SMTP_USER`.
2. Preview what would be ingested, without storing anything:

```bash
uv run wingman ingest-gmail "from:someone@company.com OR to:someone@company.com newer_than:180d" --limit 15 --dry-run
```

3. Drop `--dry-run` to store it.

- The query is normal Gmail search syntax.
- Promotions, social, updates and no-reply senders are filtered out automatically.
- The mailbox is opened read-only; Wingman never changes your mail.

### Real calendar (live feed)

1. In Google Calendar open Settings, pick your calendar, and copy "Secret address in iCal format".
2. Put it in `.env` as `WINGMAN_CALENDAR`.
3. Set `WINGMAN_ME` to your own address so you are not treated as an external attendee.
4. Check it:

```bash
uv run wingman meetings
```

- Known limit: recurring events are read by their first occurrence, so a weekly series that started in the past is skipped.

### Real notes and documents

- Put `.md`, `.txt` or `.eml` files in `data/private/` (git-ignored), then:

```bash
uv run wingman ingest data/private
```

### Use a separate brain for real data

- Set `WINGMAN_DATASET=personal` in `.env` so real data and sample data never mix.
- Wipe a dataset at any time:

```bash
uv run wingman reset
```

---

## 3-minute demo run sheet

1. `uv run wingman doctor` — six green rows. (10 s)
2. `uv run wingman graph` then `open out/brain_graph.html` — show person → company → commitment. (30 s)
3. `uv run wingman brief --next` — narrate the tool calls as they stream. (75 s)
4. `open out/dossier_priya_shah.pdf` — point at the stale alerts and the open commitment. (30 s)
5. Show the email in your inbox and `out/followup_priya_shah.md`. (15 s)
6. `uv run wingman brief --person "<a judge>" --company "<their company>" --no-writeback`. (live twist)

- **If Wi-Fi fails:** `uv run wingman render out/dossier_priya_shah.json` re-renders the last good run offline.
