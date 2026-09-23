# Wingman — Quickstart

**What it does:** reads your calendar, remembers your history with whoever you're meeting,
checks the live web for what changed, and hands you a one-page brief.

Everything below is done. **The only thing left is API keys.**

---

## 1. Get keys (5 minutes, no credit card)

You need three. Email is optional.

| What | Where | Card? |
|---|---|---|
| **Groq** — the agent's main model, ~1,000 req/day | [console.groq.com](https://console.groq.com) | No |
| **Gemini** — fallback, and powers the brain locally | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | No |
| **Bright Data** — the live web | Your hackathon code, or a free account | No |
| **Cognee** — the brain | Your hackathon code, **or skip it** and run local | No |

Open `.env` in the project root and fill in:

```bash
GROQ_API_KEY=your-groq-key
GEMINI_API_KEY=your-gemini-key
API_TOKEN=your-bright-data-token
```

Set both model keys if you can. They chain: when Groq's daily cap runs out,
Wingman moves to Gemini mid-run instead of failing.

**For Cognee, pick one.** Cloud, if you have a code:

```bash
COGNEE_CLOUD_URL=https://your-tenant.aws.cognee.ai
COGNEE_API_KEY=your-cognee-key
```

Or local, with no Cognee account at all — reuse the same Gemini key:

```bash
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-flash-latest
LLM_API_KEY=your-gemini-key
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini/gemini-embedding-001
EMBEDDING_API_KEY=your-gemini-key
```

- Set **all four** embedding lines. Changing only the LLM leaves embeddings defaulting to OpenAI.
- Cloud is faster and keeps graph building off your Gemini rate limit. Prefer it if you have the code.

## 2. Move the sample calendar to today

The bundled sample has dated meetings, so it expires overnight:

```bash
uv run wingman refresh-sample
```

## 3. Check the keys work

```bash
uv run wingman doctor
```

- Every row makes one real call, so green means it works **right now**.
- You need green on **Cognee brain**, **Bright Data web** and **LLM**. Docker and Calendar already pass.
- Email can stay yellow — briefs are saved as `.eml` files instead of sent.

## 4. Prove each layer before the big run

Do these in order. If one fails you know exactly which layer broke.

**Is the brain reachable?**

```bash
uv run wingman ask "hello"
```

**Can it remember one document?**

```bash
uv run wingman ingest data/sample --limit 1
```

**Now the rest** (add `--delay 4` if you hit rate limits):

```bash
uv run wingman ingest data/sample
```

**Does graph memory actually work?**

```bash
uv run wingman ask "What did I promise Priya Shah, and did I deliver it?"
```

You should get: a benchmark, promised by Friday 19 June, still not delivered. That answer joins
three separate documents — it's the thing plain search can't do.

## 5. Run it

```bash
uv run wingman web
```

Open http://localhost:8000 and click **Brief next meeting**.

Or from the terminal:

```bash
uv run wingman brief --next
```

---

## What you get

- `out/dossier_<person>.pdf` — the one-page brief, rendered inside a Docker sandbox
- `out/dossier_<person>.md` — the same thing as text
- `out/followup_<person>.md` — a draft reply, **never sent**
- `out/run_<timestamp>.jsonl` — every tool call, with timings
- An email to yourself, if SMTP is configured

## The dashboard

- **Left:** upcoming meetings, a box to research anyone by name, and your saved briefs
- **Middle:** the brief — what you owe them, what they owe you, what changed, stale memories, openers
- **Right:** the agent narrating itself live — what it recalled, every tool call, anything blocked
- **`/setup`:** the health checks, naming the exact variable each one needs

## Other commands

```bash
uv run wingman meetings                      # what's coming up
uv run wingman graph                         # writes out/brain_graph.html
uv run wingman brief --person "Name" --company "Co"
uv run wingman render examples/sample_dossier.json   # offline, no keys
uv run wingman reset                         # wipe the brain
```

---

## If something breaks

| Symptom | Cause | Fix |
|---|---|---|
| `doctor` says LLM SKIP | No key found | Set `GEMINI_API_KEY` in `.env` |
| Ingest is very slow | Each document builds a graph | Normal. 5–10 min for 7 files |
| Rate limit errors | A free tier hit its daily cap | Add another model key — they chain automatically |
| "no upcoming meetings" | The sample calendar expired | `uv run wingman refresh-sample` |
| `ask` hangs forever | The brain never connected | Ctrl-C, re-run `doctor` |
| Brief fails on structured output | Provider can't do the nested schema | It retries as plain JSON by itself |
| Sandbox render failed | Docker not running | Start Docker Desktop. The brief still works, Markdown only |

## Safety, by design

- Wingman **only ever emails you**. Messages to anyone else are saved as drafts.
- Generated code runs with **no network** and a read-only filesystem.
- Web spend is capped in Python at **3 searches and 3 page reads per brief** — the model cannot talk its way past it.
- Web pages and emails are treated as **data, never instructions**.
- Your real data stays in `data/private/`, which is never committed.
