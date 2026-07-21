# Week 2 — Giving the Agent Hands: Tool Calling with Grok (+ an Audio Crash Course)

**Duration**: 75–90 min · **Milestone**: M2 "Dispatcher"

## Objectives

Students leave with a cascade agent that *does things*: they understand what a tool is (and what it is not), how to declare tools with JSON schema on a Grok chat completion, how to drive the two-phase tool-call loop, and how to design tools for voice latency — fast returns, flag files, and background workers. The advanced payoff is a two-LLM architecture: the voice model files a maintenance ticket into a text file in milliseconds, and a separate worker process notices the file, drafts an email with its own Grok call, and "sends" it.

The audio/DSP material is kept as a **~15-minute flip-through crash course** at the top of the session: students get the vocabulary (PCM, 8 kHz, µ-law, frames, resampling, jitter) and know where to look when audio breaks; the full detail stays in these notes and in the starter code for reference.

## Session Shape

| Part | Time | Content |
|------|------|---------|
| Part 1 | ~15 min | Audio crash course — flip-through of the DSP slides |
| Part 2 | ~60 min | Tool calling with Grok — the meat, live-coded |

---

## Part 1 — Audio Crash Course (Slides 3–14, flip-through)

These are the original DSP slides, kept intact in the deck. Flip at ~90 seconds each; the goal is vocabulary and the mental model, not mastery. One-line takeaway per slide:

| Slide | Title | The one thing to say while flipping |
|-------|-------|-------------------------------------|
| 3 | Sound becomes numbers | Everything is a numpy array; these ten slides are here when audio breaks. |
| 4 | Sampling & quantization | An audio buffer is a numpy int16 array. That's it. |
| 5 | Why phones sound like phones | Phones are 8 kHz; models want 16 k+; your model hears worse on the phone path. |
| 6 | µ-law | 1972 log-compression; decode it to PCM *first* or you get static. |
| 7 | Frames: 20 ms pieces | Real-time audio is a metronome, not a firehose — 50 msgs/sec. |
| 8 | Resampling | Use a streaming resampler (`soxr`); persist its state across chunks or you get clicks. |
| 9 | Bytes & endianness | When audio sounds wrong: write the buffer to .wav and *look* at it. |
| 10 | Media-stream anatomy | A phone call is JSON with base64 µ-law inside. |
| 11 | Jitter & playout buffer | First appearance of the course tradeoff: latency vs. robustness. |
| 12 | AEC · NS · AGC | Clean the signal before you detect speech; order matters. |
| 13 | The full pipeline, assembled | Every arrow is a place to get bytes wrong. Keep this diagram — it's your debugging map. |
| 14 | The best pipeline is no pipeline | Some models speak µ-law natively (`audio/pcmu`) — the best transcoding is none. |

**Speaker notes for the flip**: Keep exactly one live demo from the old lecture — play the same sentence at 44.1 kHz and at 8 kHz (slide 4). It takes 40 seconds and it's the one visceral memory worth keeping. Tell students: "when your audio screeches in week 5, come back to these ten slides — today they just need to stop scaring you."

---

## Part 2 — Tool Calling with Grok (the meat)

### Slide 15 — Your Agent Is All Talk
- Week-1 Talkbox can discuss a broken heater with warmth and expertise — and *do absolutely nothing about it*
- An LLM emits text. That is the complete list of its abilities. No files, no email, no database, no phone calls
- Worse: ask it to "file a ticket" and it will cheerfully claim it did. Nothing happened. The model hallucinates *actions*, not just facts
- Tools are the fix: a contract that lets the model **request** actions that *your code* performs

**Speaker notes**: Open Part 2 by replaying this failure live: ask last week's Talkbox "please file a maintenance ticket for my broken heater" and let the class hear it lie ("I've filed that for you!"). The 2am tenant with the broken heater — our running example — doesn't want sympathy; they want a work order to exist in a system when they hang up. This slide is the *why*; everything after is *how*.

### Slide 16 — What a Tool Actually Is
- Three parts: (1) a Python function you wrote, (2) a JSON description of it you hand the model, (3) glue code connecting them
- The model **never executes anything**. It emits a structured request: "call `file_maintenance_ticket` with these arguments"
- Your code runs the function, appends the result to the conversation, and the model continues
- Mental model: the LLM is a brain in a jar; tools are nerves *you* solder on — and you choose how many, and where

**Speaker notes**: This kills the #1 misconception (that the model somehow runs code). It also carries the security lesson for free: a tool call is a *request* from an untrusted narrator; your code is the one with hands, so your code validates. "Initializing" a tool = writing the function + writing its schema + registering both, nothing more magical than that.

### Slide 17 — Declaring a Tool: The Schema
- Same `chat.completions.create` call as week 1, plus a `tools=[...]` parameter
- Each entry: `{"type": "function", "function": {"name", "description", "parameters"}}` — `parameters` is JSON Schema
- **Descriptions are prompts.** The model decides *whether* and *how* to call your tool by reading them
- Constrain what you can: `"enum": ["emergency", "urgent", "routine"]` beats a free-text `urgency` string

**Speaker notes**: Put the real schema from the scaffold on screen (`file_maintenance_ticket`: unit, problem, urgency). Line-by-line: the `name` must match your dispatcher; the `description` tells Grok *when* to reach for it ("Use when a tenant reports something broken…"); `required` fields force the model to ask the caller for missing info instead of inventing it — which is exactly the conversational behavior you want on a phone call.

### Slide 18 — The Tool-Call Loop
- Round 1: model answers with `finish_reason: "tool_calls"` instead of text — arguments arrive as a **JSON string** you must parse
- You: execute each call → append the assistant's tool-call message *and* a `role: "tool"` result message (matched by `tool_call_id`)
- Round 2: model reads the results and finally produces the words to speak
- It's a **loop**, not an if: the model may chain tools (file a ticket, then check it). Cap the rounds

**Speaker notes**: Whiteboard the message list growing: `[system, user] → +assistant(tool_calls) → +tool(result) → +assistant(text)`. The two bugs everyone hits: forgetting to append the assistant tool-calls message before the tool result (the API rejects the history), and passing `arguments` to the function without `json.loads`. Say both now; they'll hit them anyway; at least they'll recognize the error.

### Slide 19 — Tools Force Memory
- Week-1 Talkbox was stateless: every question a blank slate
- The tool loop is a conversation *within* one turn; follow-ups ("did you file it?", "what's the status?") need history *across* turns
- Keep a running `messages` list; append the user turn and the final assistant turn each round trip
- "What's the status of my ticket?" only works if the agent remembers filing it — or has a tool to look it up (do both)

**Speaker notes**: In-RAM history is fine for the course (one user per server). Note the production shape without building it: per-call session state, persisted, because phone calls drop and people call back — that's week 6 material. The status-check tool is also the first *read* tool students write, next to the *write* tool — good pairing to show tools aren't only side effects.

### Slide 20 — Voice + Tools = Latency Discipline
- Every tool round trip adds a full extra LLM call — your "brain" stage roughly **doubles** when a tool fires
- And while your tool runs, the caller hears **silence**
- Rule for the voice path: a tool returns in **under ~100 ms**
- Slow or risky work — sending email, CRM writes, payments — must *never* run inside the tool

**Speaker notes**: Show it on the scaffold's latency bar: ask a no-tool question, then a ticket-filing question, and watch the Grok segment double. This is why the milestone architecture exists: the tool's job is to *record the intent durably and return*. The actual work happens elsewhere. Foreshadow week 4: filler phrases ("one moment, let me file that…") buy you time the same way.

### Slide 21 — The Flag-File Pattern
- `file_maintenance_ticket` appends **one JSON line** to `tickets/inbox.jsonl` and returns the ticket id — microseconds, durable
- A completely separate process — `worker.py` — polls that file and picks up tickets it hasn't seen
- The worker drafts an email with **its own Grok call** and delivers it to an outbox
- You just built a job queue out of a text file. Production swaps the file for Redis/SQS and the outbox for real SMTP — **same shape**

**Speaker notes**: Two failure-isolation wins to spell out: if the worker crashes, the phone call is unaffected and the ticket is still in the file (retry later); if the call drops, the ticket already survived. The `processed.txt` ledger the worker keeps is at-least-once delivery + idempotency, taught with two text files. Students who've used Celery/SQS will smile; students who haven't just learned the concept with `tail -f`.

### Slide 22 — Two Brains: Why the Worker Gets Its Own LLM
- Voice Grok is prompted to *converse*: short spoken sentences, no formatting
- Worker Grok is prompted to *produce an artifact*: a professional work-order email, subject line, all ticket details — no length pressure, no latency pressure
- Different prompts, different jobs; the ticket file is the **contract** between them
- The worker call is one-shot LLM-as-function: JSON in → email out. No conversation, no history

**Speaker notes**: This is students' first multi-LLM system, and the framing to plant: an LLM call is just another kind of function — you'll sprinkle them anywhere a fuzzy transformation is needed. Mention you can point the worker at a cheaper/smaller model since nobody is waiting on it; that's a real cost lever in production.

### Slide 23 — Tool Design Rules for Voice
- Few tools with sharp descriptions beat many vague ones (3 good > 12 mushy — tool *choice* is a model skill you can sabotage)
- **Validate every argument.** The model *will* invent a unit number rather than ask, unless schema + prompt tell it not to
- Return terse JSON the model can speak from (`{"ticket_id": "T-1042", "status": "filed"}`), not a data dump
- Return errors as strings, too — the model reads `{"error": "unknown unit"}` and *asks the caller to clarify*. That's error handling you get for free
- Log every tool call with arguments: this is your transcript of *actions*, and in regulated verticals it's your audit trail

**Speaker notes**: The error-as-string trick deserves 60 seconds: raising an exception kills the turn; returning `{"error": ...}` turns failure into conversation ("Hmm, I don't see a unit 9C — can you double-check the number?"). Property management, healthcare, finance: the action log is what compliance actually asks for.

### Slide 24 — Milestone 2: "Dispatcher"
- Scaffold = week 1's Talkbox with the cascade **already implemented** (it was your homework) + conversation memory + an empty tool belt + a worker skeleton
- You write four things: two tool schemas, the two Python functions (`file_maintenance_ticket` → append to `tickets/inbox.jsonl`; `check_ticket_status` → read it back), the tool-call loop, and the worker's Grok email draft
- Definition of done: tell it "my heater is broken, unit 4B, it's freezing" → it speaks a confirmation with a ticket id → an email appears in `outbox/` within seconds → "what's the status of my ticket?" gets a correct spoken answer
- Stretch: real SMTP delivery; conditional routing (emergency → on-call email now, routine → daily digest); a third tool of your choosing

**Speaker notes**: The scaffold works out of the box as a talkbox-with-memory (step 0, nothing to configure beyond last week's `.env`), and the worker runs out of the box in **template mode** — it emails a boring fixed template until students upgrade `draft_email()` to a Grok call. Same echo-first philosophy as week 1: plumbing proven before they touch the new concept. Demo the full loop in class with three terminals: server, `worker.py`, and `tail -f tickets/inbox.jsonl outbox/*.eml`.

### Slide 25 — Homework & Reading
- M2 "Dispatcher" due before week 3
- Deliverable: the conversation transcript, the ticket line from `inbox.jsonl`, and the generated email — for one urgent and one routine request
- Conceptual: "Why must `file_maintenance_ticket` return *before* the email is drafted? Trace what the caller hears if it didn't."
- Conceptual: "Your agent filed the same heater ticket twice in one call. What probably went wrong, and what do you change — the schema, the prompt, or the function?"
- Reading: xAI function-calling docs (docs.x.ai); skim your provider-of-choice's outbound email API for the stretch goal

## Live Demo Plan
1. **The lie** (open of Part 2): ask week-1 Talkbox to file a ticket; let the class hear it claim success
2. One kept audio demo during the flip: the same sentence at 44.1 kHz vs 8 kHz
3. Live-code a trivial `get_time` tool onto Talkbox (~15 lines): schema, loop, and the two-round-trip log output on screen
4. Full Dispatcher run with three terminals: talk → ticket line appears in `tail -f` → worker wakes → email lands in `outbox/`

## Common Pitfalls
- Forgetting to append the assistant tool-calls message before the `role:"tool"` result — the API rejects the malformed history
- `tool_call.function.arguments` is a JSON **string**, not a dict — `json.loads` it
- An unbounded tool loop when the model keeps calling tools — cap the rounds and bail gracefully
- The worker reprocessing the whole inbox on every poll — track processed ticket ids
- The model reading raw JSON aloud — tell it in the system prompt to confirm naturally in words
- Two tools with overlapping descriptions — the model dithers or calls both; sharpen the wording
