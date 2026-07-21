# Week 2 Code Walkthrough — teaching the Dispatcher scaffold alongside the slides

Instructor-facing. Maps the scaffold to the week-2 deck (Part 2, slides
15–25). Part 1 (the audio flip-through, slides 3–14) has no code component —
keep one demo (44.1 kHz vs 8 kHz) and move on. Total live coding/demo time:
~35 minutes across four segments.

## Before class

- Have week 1's Talkbox running in a terminal (for the opening failure demo)
  and the week-2 **solution** configured (for the closing demo).
- Three visible terminals for the finale: server · worker · `tail -f`.
- Delete stale `tickets/` and `outbox/` so ids start fresh at T-1000.

---

## Segment A · Slide 15 ("your agent is all talk") — the opening failure

**Show:** week 1's Talkbox. Ask it, out loud: *"Please file a maintenance
ticket for my broken heater, unit 4B."*

**Teach:**

- It will answer warmly and claim success — "I've filed that for you!" —
  and absolutely nothing happened anywhere. Let the silence land.
- Name the phenomenon: the model hallucinates **actions**, not just facts.
  Text out is its only ability; everything else needs a contract.
- This is the week's arc: by the end of class the same sentence produces a
  ticket id you can `cat`, and an email you can open.

---

## Segment B · Slides 16–18 — live-code a trivial tool onto Talkbox (~15 min)

Before touching the Dispatcher scaffold, add a `get_time` tool to week 1's
Talkbox live. ~15 lines, no file I/O, and the class sees the whole mechanism
naked. Keep the log window visible so both round trips are on screen.

```python
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Get the current local time. Use when asked what time it is.",
        "parameters": {"type": "object", "properties": {}},
    },
}]

# inside the llm stage:
msg = client.chat.completions.create(model=..., messages=msgs, tools=TOOLS).choices[0].message
if msg.tool_calls:
    msgs.append({"role": "assistant", "content": msg.content,
                 "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
    msgs.append({"role": "tool", "tool_call_id": msg.tool_calls[0].id,
                 "content": time.strftime("%H:%M")})
    msg = client.chat.completions.create(model=..., messages=msgs, tools=TOOLS).choices[0].message
reply_text = msg.content
```

**Teach, while typing:**

- Slide 16: point at each of the three parts — function (`time.strftime`),
  description (the schema), glue (the if-block). "The model never ran
  anything; it asked, we ran, it spoke."
- Slide 17: change the description to something vague ("gets time data") and
  show the model getting hesitant or skipping the tool. **Descriptions are
  prompts** — this 30-second A/B is the most convincing demo of the day.
- Slide 18: show the raw first response on screen: `finish_reason:
  "tool_calls"`, and `arguments` as a *string*. Then deliberately delete the
  assistant-message append and run it — let the class see the 400. They will
  all hit this bug; now they'll recognize it.
- Ask "what time is it?" twice and compare latency bars with a no-tool
  question — the Grok segment doubles (Slide 20's point, measured live).

---

## Segment C · Slides 19–23 — the Dispatcher scaffold tour

**Show:** `server.py` top-down, then `worker.py`.

### 1. `HISTORY` + `SYSTEM_PROMPT` (Slide 19)
- Week 1 was stateless; the module-level `HISTORY` list is the upgrade, and
  the page's "new call" button is just `HISTORY.clear()`.
- Read the system prompt aloud — it encodes this week's behaviors: collect
  unit + problem, ask rather than guess, never read raw JSON, confirm the
  ticket id in words. Prompt and schema work as a team.

### 2. `TOOLS` (Slide 17) — the provided schema, line by line
- `description`: "Use whenever a tenant reports something broken…" — when-to-
  use language, not what-it-does language.
- `urgency` enum: constrain what you can; the classifier lives in the schema.
- `required`: this is what makes the model *ask the caller* for a missing
  unit number instead of inventing one.
- Students write the second schema (`check_ticket_status`) themselves — a
  read tool next to the write tool, on purpose: tools aren't only side effects.

### 3. `run_tool()` (Slide 23) — errors as conversation
- It never raises: failures return as `{"error": ...}` strings the model
  reads and repairs conversationally ("I don't see a unit 9C — can you
  double-check?"). Exception → dead turn; error-string → dialogue.
- The `log.info` on every call is the *action* transcript — in regulated
  verticals, this line is what compliance asks for.

### 4. `think()` (Slide 18) — step 0 + the loop skeleton
- As shipped it's one plain call: the scaffold talks before any homework.
  Same echo-first philosophy as week 1.
- Walk the commented loop: the append-order trap, `json.loads`, and
  `MAX_TOOL_ROUNDS` (it's a loop, not an if — the model may file then check).

### 5. `worker.py` (Slides 21–22) — the other half
- The tool appended one line and returned in microseconds; *this* process
  does the slow part. Poll → skip processed ids → draft → send → record.
- `processed.txt` is the ledger: at-least-once delivery + idempotency,
  implemented with a text file. The ledger advances **only on success**, so
  a failed draft retries next poll — free retry semantics.
- `draft_email()` ships as a template (worker runs with no key at all);
  homework 4 upgrades it to a Grok call with its **own prompt**. Put
  `DRAFTER_PROMPT` and the server's `SYSTEM_PROMPT` side by side on screen:
  same API, opposite instructions — that's Slide 22's "two brains" in code.
- Mention `WORKER_MODEL`: nobody waits on the worker, so it can be a
  smaller, cheaper model. Real cost lever in production.

---

## Segment D · Slide 24 — the full-loop demo (the finale)

Three terminals visible: server, `python solution/worker.py`, and
`tail -f tickets/inbox.jsonl`. Then, out loud:

> "Hi, my heater is broken in unit 4B and it's freezing in here."

The class watches, in order: the tool chip appear in the browser → the JSON
line hit the `tail` → the worker log "EMAIL SENT" → open the `.eml` and read
Grok's drafted work order. Then ask *"what's the status of my ticket?"* and
let the status tool find the outbox file and answer "dispatched."

Close on the contrast with Segment A: same sentence, but now something is
true in the world afterward.

## What to collect (Slide 25)

1. Working Dispatcher (talk to it; one random "explain this function").
2. Transcript + ticket line + email for one urgent and one routine request.
3. The two conceptual questions — the "why must the tool return first"
   answers preview week 4's filler-phrase material; keep the good ones.

## Anticipated student questions

- *"Why not just have the tool send the email?"* — It works in the demo and
  fails on the phone: the caller sits in silence for the whole SMTP+LLM
  round trip. The tool records intent; the worker acts. (Also: crash
  isolation — worker dies, call survives.)
- *"Why does the model sometimes ask for the unit instead of calling the
  tool?"* — `required` + the system prompt told it to. That's correct
  behavior, not a bug; celebrate it.
- *"Can the model call both tools in one round?"* — Yes, `tool_calls` is a
  list; the loop handles it. That's why the results are matched by
  `tool_call_id`.
- *"Isn't polling a file ugly?"* — It's the honest version of every queue
  you'll ever use. Swap file→Redis and poll→BLPOP and the architecture
  diagram doesn't change.
- *"What if two servers write the file at once?"* — Appends this small are
  atomic on POSIX, and we have one server. The real answer is "that's when
  you graduate to a real queue" — week 6 touches production shapes.
