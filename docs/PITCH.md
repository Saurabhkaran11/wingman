# Wingman — Pitch, Demo and Speech

- Event: Battle of the Personal Brains, Bright Data office, San Francisco, 2026-09-21.
- Slide deck: 12 slides, speaker notes on every slide (link in the chat where this was made).
- Everything here is written in plain words for saying out loud.

---

## 1. The one-minute speech

About 165 words. Speak at a normal pace and it lands at 60 seconds.

> Hi, I'm Karan.
>
> Tomorrow I have coffee with someone I emailed three months ago. I don't remember what we talked about. I don't remember what I promised her. And I have no idea what has changed at her company since.
>
> That's the problem Wingman fixes.
>
> Wingman is a personal agent that preps you before every meeting. It reads your calendar. It remembers your history with each person from your own emails and notes. It checks the live web for what's new. Then it hands you a one-page brief: who they are, what you last talked about, what you owe each other, and what has changed.
>
> If your notes are out of date, it tells you. It emails you the brief and drafts your follow-up.
>
> Under the hood: Cognee is the memory. Bright Data is the eyes on the web. Strands runs the loop. Docker keeps generated code in a box.
>
> There is no chat box. Your calendar goes in. A brief comes out.
>
> Let me show you.

### A 30-second version, if time is cut

> I have a meeting tomorrow with someone I barely remember. Wingman reads my calendar, remembers our history from my own emails, checks the web for what's new, and hands me a one-page brief. If my notes are out of date, it flags it. Then it emails me the brief and drafts my follow-up. No chat box. Calendar in, brief out.

---

## 2. The short demo (about 90 seconds)

Run every command from the project root. Have a terminal, the PDF viewer and your inbox open before you start.

| Step | Say | Do | Time |
|---|---|---|---|
| 1 | "Here's my calendar. Coffee with Priya tomorrow. I remember nothing." | `uv run wingman meetings` | 10 s |
| 2 | "One command. Watch it think out loud." | `uv run wingman brief --next` | 45 s |
| 3 | While it runs: "It pulled my memory first. Now it's searching the web. There, it hit the search cap. That cap is Python, not a prompt." | Point at the `[memory]`, `[hook]`, and `[steering]` lines | during step 2 |
| 4 | "Here's the brief." | `open out/dossier_priya_shah.pdf` | 15 s |
| 5 | "My notes said Cognee had no cloud product. The web says Cognee Cloud is live. And I owe her a benchmark that's three months late." | Point at the stale memory alert and the open promise | during step 4 |
| 6 | "The brief is in my inbox, and the apology is already drafted." | Show the email and `out/followup_priya_shah.md` | 10 s |
| 7 | Live twist: "Give me a name." | `uv run wingman brief --person "Name" --company "Company" --no-writeback` | 45 s, only if time allows |

### Rules for the live twist

- Ask the volunteer first.
- Public, professional information only.
- Keep `--no-writeback` so a stranger's details stay out of your brain.

### If the Wi-Fi dies

This needs no keys and no network beyond Docker:

```bash
uv run wingman render examples/sample_dossier.json
open out/dossier_priya_shah.pdf
```

Say: "Same brief, rendered from a cached run." Then continue from step 5.

### Before you go on stage

- Run `uv run wingman doctor` and get six PASS rows.
- Do one full `brief --next` run so the brain is warm and a fresh PDF exists in `out/`.
- Clear the terminal. Bump the font size.

---

## 3. The deck, slide by slide

| # | Slide | The one idea |
|---|---|---|
| 1 | Cover | Wingman briefs you before every meeting. |
| 2 | Problem | You walk into meetings cold: history is scattered, their world changes, nobody has time. |
| 3 | What it does | Reads calendar, remembers history, checks web, hands you a brief. |
| 4 | The brief | One page: who, last time, what you owe each other, what changed, alerts, talking points. |
| 5 | The moment | Stale memory alert plus the forgotten promise. |
| 6 | How it works | Cognee, Strands, Bright Data, Docker sandbox, actions. |
| 7 | Guardrails | Caps and rules are Python, checked before a tool runs. |
| 8 | Not a chatbot | Calendar in, PDF out, and it learns. |
| 9 | Demo | The run sheet above, on one slide. |
| 10 | Judges | The five judging questions, one line each. |
| 11 | Next | Live connectors, morning run, post-meeting mode, relationship health. |
| 12 | Close | "My brain remembers, checks itself against the world, and does the prep for me." |
