# M2 — "Dispatcher": tools, a flag file, and a worker with its own brain

**Due before week 3.** Definition of done: tell the agent "my heater is
broken, unit 4B, it's freezing" → it speaks a confirmation with a ticket id →
an email appears in `outbox/` within seconds → ask "what's the status of my
ticket?" → it answers correctly. Graded on behavior, not style.

This week your agent stops being all talk. Week 1's cascade is **provided**
(it was your homework); what you build is the tool belt and the worker.

## What's in the box

| File | Status | What it is |
|------|--------|------------|
| `server.py` | **you edit 3 marked spots** | the cascade + memory, provided; you write the tool schemas, the tool functions, and the tool-call loop |
| `worker.py` | **you edit 1 marked spot** | watches `tickets/inbox.jsonl`, emails work orders; you upgrade `draft_email()` from a template to a Grok call |
| `static/index.html` | provided | week 1's page + tool chips + a "new call" button |
| `.env.example` | copy to `.env` | same values as week 1 (+ optional worker settings) |

## The architecture you're building

```
you speak ──> STT ──> Grok + TOOLS ──> TTS ──> you hear
                        │ file_maintenance_ticket()      (fast: append one line)
                        ▼
              tickets/inbox.jsonl  ◄── the flag file / job queue
                        │
                        ▼ (polled every 2 s, separate process)
                    worker.py ──> Grok (its own prompt) ──> outbox/T-1042.eml
```

Two LLMs, two processes, decoupled by a text file. The voice path stays fast
because the tool only *records the intent*; the slow work (drafting, sending)
happens where nobody is waiting on hold.

## Setup & run (three terminals)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # same key/model/voice as week 1

uvicorn server:app --reload --port 8000   # terminal 1 — the agent
python worker.py                          # terminal 2 — the worker
tail -f tickets/inbox.jsonl               # terminal 3 — watch the flag file
```

Open **http://localhost:8000** (localhost only, as always).

## The recommended path

1. **Step 0 — it already talks.** As shipped, the server is week 1's Talkbox
   *with conversation memory* and the worker runs in **template mode** (no
   LLM). Prove both: have a two-turn conversation, then append a fake ticket
   and watch the worker email it:
   ```bash
   mkdir -p tickets && echo '{"id":"T-999","unit":"1A","problem":"test","urgency":"routine","filed_at":0}' >> tickets/inbox.jsonl
   # worker terminal: "EMAIL SENT -> outbox/T-999.eml"
   ```
2. **HOMEWORK 1 — schemas.** `file_maintenance_ticket`'s schema is written
   for you (read it line by line — descriptions are prompts). Write the
   schema for `check_ticket_status` yourself.
3. **HOMEWORK 2 — the functions.** Both are a few lines of file I/O. Rules:
   return in <100 ms, return terse JSON strings, validate arguments.
4. **HOMEWORK 3 — the loop.** Replace `think()`'s single call with the
   tool-call loop (skeleton in comments). The two classic bugs, so you
   recognize them: forgetting to append the assistant's tool-call message
   before the tool result, and forgetting `json.loads` on the arguments.
5. **HOMEWORK 4 — the worker's brain.** Upgrade `draft_email()` from the
   template to a one-shot Grok call with its own system prompt.

## Deliverables

- The conversation transcript, the ticket line from `inbox.jsonl`, and the
  generated email — for one **urgent** and one **routine** request
- Conceptual: why must `file_maintenance_ticket` return *before* the email is
  drafted? Trace what the caller hears if it didn't.
- Conceptual: your agent filed the same heater ticket twice in one call.
  What probably went wrong — the schema, the prompt, or the function?

**Stretch:** real SMTP delivery (`send_email()` is the only function to
touch); conditional routing (emergency → email now, routine → daily digest);
a third tool of your choosing.

## Common failures

- **400 from chat completions after a tool call** — you appended the
  `role:"tool"` result without the assistant's tool-call message before it.
- **`TypeError` in your tool function** — `tc.function.arguments` is a JSON
  *string*; parse it.
- **Worker re-emails everything on restart** — you marked processed in
  memory, not in `tickets/processed.txt`.
- **Agent reads JSON aloud** — your system prompt needs "never read raw
  JSON; confirm naturally in words."
- **Agent invents a unit number** — tighten the schema description and the
  system prompt ("ask for anything missing rather than guessing"), and
  validate in the function.
