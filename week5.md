# Week 5 — Going Native: The Voice Agent API & Real-Time Reliability

**Duration**: 90 min (the densest week) · **Milestone**: M5 "Survivor"

## Objectives

Students replace their hand-built cascade with a native speech-to-speech session (xAI Grok Voice Agent API), master the realtime event protocol (session config, audio streaming, function calling, barge-in), and add the reliability layer that separates demos from products: watchdogs, reconnection, and resumption.

## Slide-by-Slide

### Slide 1 — Title: "Going Native (and Staying Alive)"
- Part 1: replace three API calls with one WebSocket
- Part 2: everything fails mid-sentence — build for it

**Speaker notes**: Frame the irony: they've spent four weeks building and refining a cascade; today they'll delete half of it. That's not wasted work — the cascade is still what they'll debug with, fall back to, and use on text channels. And every concept from weeks 1–4 (formats, VAD, endpointing, tools) is about to reappear as literal JSON fields.

### Slide 2 — The Voice Agent API Mental Model
- One WebSocket: `wss://api.x.ai/v1/realtime?model=grok-voice-latest` (Bearer auth; ephemeral client secrets for browser-side connections)
- Everything is a typed JSON event, both directions
- You stream mic audio up (`input_audio_buffer.append`); the model streams speech down (`response.output_audio.delta`)
- STT, VAD, endpointing, LLM, and TTS all live server-side now — you configure them instead of building them
- Protocol is OpenAI-Realtime-compatible: same event names, mostly

**Speaker notes**: Show a raw event log of a real 20-second session — just the event *types* scrolling by. Students should recognize the anatomy: session lifecycle, audio deltas, VAD events, transcription events.

### Slide 3 — The Handshake (Order Matters)
- 1. Open WebSocket → server sends `conversation.created`
- 2. You send `session.update` with your full config
- 3. Server confirms with `session.updated` → **only now** is it safe to stream audio
- Race-condition lesson: audio sent before the session is configured is audio processed with the wrong settings — gate your send loop on a `ready` flag
- Then optionally trigger a greeting (`response.create` with one-off instructions: "open with this line, then stop")

**Speaker notes**: This ready-flag gating is the first of several "distributed systems in miniature" lessons this lecture. A subtle real-world bug: greeting via a fake user message makes the model *echo and elaborate*; greeting via one-off response instructions makes it say the line once. Small protocol choices, audible differences.

### Slide 4 — `session.update`: Week 2 and 3 as JSON
- `instructions` (system prompt), `voice` (eve, ara, rex, sal, leo, or custom)
- `audio.input/output.format.type`: `audio/pcm` (pick a rate) or `audio/pcmu` (µ-law 8 kHz — the phone codec, week 2!)
- `turn_detection`: `server_vad` with `threshold`, `silence_duration_ms`, `prefix_padding_ms`, `idle_timeout_ms` (week 3!)
- `tools`: your function schemas — same shapes as week 4
- Extras worth knowing: transcription `language_hint` + `keyterms` (domain vocabulary), pronunciation `replace` map, output `speed`, `reasoning.effort`

**Speaker notes**: This slide is the payoff for the whole course structure: nothing here is new, it's weeks 2–4 rendered as config. Match input/output rates to your actual pipeline to avoid pointless resampling (browser: 24 kHz PCM is comfortable; telephony: pcmu passthrough). The `keyterms` feature solves week 4's pronunciation/recognition pain for domain words — give a concrete example like unit codes or street names.

### Slide 5 — Barge-In, For Real This Time
- Server VAD emits `input_audio_buffer.speech_started` the instant the caller starts talking over the agent
- Your job on that event: stop local playback, flush every downstream buffer (send `clear` to the browser/provider), drop any queued deltas
- The model handles its own side (stops generating); you handle yours (stop *playing*)
- Test it live: interrupt your agent mid-monologue; it should go silent in ~100–300 ms

**Speaker notes**: Recall the week-3 buffer-chain drawing. The event does the *detection* for you; the *reaction* is still entirely your code, and a missed buffer is still audible. This is an M5 grading item — the TA will interrupt the agent.

### Slide 6 — Function Calling Over the Wire
- Model emits `response.function_call_arguments.done` → carries `name`, `call_id`, `arguments` (JSON string)
- You execute, then send `conversation.item.create` with `type: "function_call_output"` + the `call_id`
- Then `response.create` to make the model speak the follow-up
- **The double-reply bug**: one model turn can contain *multiple* function calls. If you trigger `response.create` per tool result, the model speaks once per tool. Correct pattern: submit all outputs as they arrive, then send exactly **one** `response.create` when the turn finishes (`response.done`)

**Speaker notes**: The double-reply bug is a genuine field bug — walk it as a war story ("the agent answered every question twice and we couldn't hear why in the logs until we counted `response.create`s"). It teaches the deeper lesson: in event protocols, correctness lives in *when* you send, not just *what*.

### Slide 7 — Scripted Speech: `force_message`
- Sometimes the model must say an *exact* line: legal disclosures, verification prompts, structured surveys
- `conversation.item.create` with `type: "force_message"` → straight TTS of your text, no model involvement, optionally `interruptible: false`
- It emits a full response lifecycle (created → audio deltas → done), so your relay code handles it unchanged
- Pattern: model speaks the empathy, `force_message` speaks the compliance

**Speaker notes**: This xAI-specific extension solves a real product problem: LLMs paraphrase, and some words legally can't be paraphrased. Also flag the interaction rule: a force_message *is* the turn — don't follow it with `response.create` or you'll get bonus improvisation.

### Slide 8 — Part 2: Everything Fails Mid-Sentence
- Failure taxonomy for a live call: model stalls (connection open, no events), WebSocket drops, provider/browser side drops, your own event loop blocks
- Phone-call physics: the caller hears *silence* for all of these — they can't tell a stall from a hangup
- Reliability layer = detect fast, react in order of increasing severity, never leave dead air
- "A voice agent's uptime is measured per-sentence"

**Speaker notes**: Keep this generic and conceptual (taxonomies and principles). Every production voice system grows a reliability layer; the details are where the scars are.

### Slide 9 — Watchdogs
- Pattern: record the timestamp of every event received from the model; a background task checks "how long since the last event?" against thresholds
- Context-aware thresholds: "user finished talking N seconds ago and no response started" is a different (tighter) condition than "no events at all for M seconds"
- Beware false positives: no events *while your own audio is still playing* is normal — the watchdog must know the playback state (week 3's state machine, again)
- Escalation ladder: verbal nudge → reconnect → graceful goodbye. Never just go silent

**Speaker notes**: The false-positive point is the hard-won one: a naive watchdog fires during long agent utterances and "recovers" a healthy call into a broken one. The turn-taking state machine from week 3 is what makes a watchdog smart. Keep thresholds as "tune for your product" — the numbers are less important than the structure.

### Slide 10 — Reconnection Without Amnesia
- A dropped WebSocket ≠ a dropped call: telephony/browser side is still live — you can reconnect to the model mid-call
- Reconnect with exponential backoff; keep accepting (and buffering) caller audio while reconnecting
- The amnesia problem: a fresh session has no memory of the call so far
- xAI's answer: session `resumption` — enable it, capture `conversation.id` from `conversation.created`, reconnect with `?conversation_id=...` and prior turns replay
- Cascade's answer (week 4): you own the history; just resend it. Native APIs need explicit resumption support — a real architectural tradeoff

**Speaker notes**: Close the loop to slide 8 of week 4 (state layers): this is why "the world" lives in your database — resumption covers conversation memory, but a booked appointment must survive even a *failed* resumption.

### Slide 11 — Don't Block the Loop
- Your server is one asyncio event loop shuttling 20 ms frames in both directions — a single 200 ms synchronous call (database! logging! JSON on a huge object!) audibly stutters *every* concurrent call
- Rules: `await` everything; push CPU work (resampling, VAD) into C-extension libraries or executors; never do file/network I/O inline in the audio path
- Pacing: send audio to the browser/provider at a fixed cadence from a buffer, not in bursts as the model produces it — smooth playback and instant flush on barge-in
- Observability: log every event type with timestamps; save transcripts; record audio (with consent) — you cannot debug what you didn't capture

**Speaker notes**: The "one blocking call stutters every call" line is the concurrency lecture in one sentence. If time allows, show an event-loop blocking demo: add `time.sleep(0.2)` in a handler and let them hear the glitch.

### Slide 12 — Milestone 5: "Survivor"
- Replace the M4 cascade with a Voice Agent API session: browser mic → your server → xAI realtime WS → back
- Keep your week-4 tool working over the new protocol (function_call_output flow)
- Implement barge-in (`speech_started` → flush) — TA will interrupt the agent
- Implement a watchdog: kill the model WS mid-call (we'll show you how to simulate) → agent must recover or say goodbye, never dead air
- Definition of done: conversation works, interruption works, simulated failure is handled audibly
- Stretch: session resumption on reconnect; `force_message` greeting; keyterms for your domain vocabulary

**Speaker notes**: Failure simulation levels the playing field: give students a provided `chaos.py` that randomly closes their model WebSocket. Watching their own agent survive a chaos test is the most satisfying moment of the course.

### Slide 13 — Homework & Reading
- M5 due before week 6; demo-day signup
- Conceptual question: "Your watchdog fires while the agent is mid-sentence on a healthy call. What state was it missing, and how do you fix it?"
- Conceptual question: "Compare how the cascade (M4) and the native session (M5) each recover conversation memory after a disconnect. Which do you trust more, and why?"
- Optional: xAI docs on ephemeral client secrets (browser-direct connections — how you'd cut your server out of the audio path entirely)

## Live Demo Plan
1. Raw event-type stream of a live session (slide 2)
2. Live barge-in demo — interrupt the agent mid-monologue
3. The double-reply bug, reproduced (two tools + naive per-tool response.create), then fixed
4. Chaos test: kill the model WS mid-call, watch the agent recover

## Common Pitfalls
- Streaming audio before `session.updated` (config race)
- Barge-in that flushes the server buffer but not the browser's playout buffer (agent "keeps talking")
- `response.create` after every tool output (double-reply bug)
- Forgetting that `force_message` is its own turn
- Watchdog with no playback-state awareness (false positives)
