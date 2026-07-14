# Week 3 — Turn-Taking: VAD, Endpointing, and Interruptions

**Duration**: 75–90 min · **Milestone**: M3 "Listener"

## Objectives

Students understand that "knowing when the user is talking, and when they're done" is a distinct, hard subproblem — arguably the one that most determines whether a voice agent feels natural. They can implement VAD, reason about endpointing tradeoffs, and explain barge-in.

## Slide-by-Slide

### Slide 1 — Title: "The Hardest Problem Nobody Talks About"
- "Your agent doesn't just need to understand speech. It needs to know when to shut up and when to start."

**Speaker notes**: Open with two failure demos (recordings or role-play): (1) an agent that interrupts the user mid-sentence, (2) an agent that leaves 4 seconds of dead air. Both had perfect speech recognition. Turn-taking is a separate axis of quality.

### Slide 2 — What Is a "Turn"?
- Human conversation: turns exchange in ~200 ms gaps — faster than reaction time, so humans *predict* turn ends
- Backchannels: "uh-huh," "right" — speech that is not a turn claim
- Mid-thought pauses: "my address is… four two…" — silence that is not a turn end
- Overlap and interruptions are normal, not errors

**Speaker notes**: The punchline: silence alone cannot define a turn boundary, yet silence is mostly what our algorithms measure. Everything this week is coping strategies for that gap.

### Slide 3 — Voice Activity Detection: The Three Generations
- **Energy threshold**: "is it loud?" — trivial, fails on any background noise
- **Classical statistical** (e.g., `webrtcvad`): fast, tiny, frame-based (10/20/30 ms), tunable aggressiveness modes — good first-pass filter
- **Neural** (e.g., Silero VAD): a small model, dramatically better at speech-vs-noise, still cheap enough to run per-frame on CPU
- Production pattern: cheap VAD as a fast gate, neural VAD for decisions that matter

**Speaker notes**: Live demo Silero on the room mic if feasible: show the speech-probability meter reacting to speech vs claps vs keyboard noise. Mention the two-tier pattern is a real production design: don't spend neural inference on obvious silence.

### Slide 4 — VAD Errors and Their Costs
- False positive (noise flagged as speech): agent stops talking for a door slam; garbage gets streamed to the model
- False negative (speech flagged as silence): agent talks over the user; words get clipped off the start of utterances
- Tuning knob: aggressiveness/sensitivity — you are choosing *which error you prefer*
- There is no setting that eliminates both; pick per product context

**Speaker notes**: Give the concrete asymmetry: for a phone agent, talking over the caller is far worse than a moment of extra patience — most production tuning leans patient.

### Slide 5 — Endpointing: Deciding the User Finished
- Endpointing = declaring "the turn is over, respond now"
- Core algorithm: track speech→silence transition; wait for N ms of continuous silence; then commit
- These are literal API parameters — xAI Voice Agent API `turn_detection` (type `server_vad`): `threshold` (VAD sensitivity, 0.1–0.9), `silence_duration_ms` (silence before the turn ends), `prefix_padding_ms` (audio kept from before speech onset, so first syllables survive), `idle_timeout_ms` (re-engage a silent caller)
- Gemini Live exposes the same ideas under different names (start/end-of-speech sensitivity, prefix padding, silence duration) — learn the concepts, map the names
- Every ms of required silence is a ms added to *every single response* — endpointing is usually the biggest chunk of perceived latency

**Speaker notes**: Connect to the week-1 latency budget: model inference might take 400 ms, but a conservative 800 ms endpoint delay doubles perceived latency before the model even starts. This is where "snappy" and "patient" fight. In week 5 students will set these exact JSON fields in their own `session.update` message — flag that so they know this slide is directly actionable.

### Slide 6 — The Patience Dial
- Diagram: a single slider from "eager" to "patient"
- Eager: snappy responses, but interrupts slow talkers, splits utterances ("I live at… ") into two turns
- Patient: never interrupts, but dead air after every turn
- Context-dependent: elderly callers, non-native speakers, people reading out numbers → lean patient; quick confirmations → lean eager
- Advanced: adapt dynamically (longer patience when the user is mid-list or mid-number)

**Speaker notes**: This slide is deliberately product-thinking, not code. Real deployments tune this per audience and it changes user satisfaction more than model choice does.

### Slide 7 — Semantic Endpointing (Where the Field Is Going)
- Silence-based endpointing is blind to *content*
- Semantic endpointing: use the transcript-so-far to judge completeness — "I live at" is obviously unfinished
- Native speech-to-speech models increasingly do this internally; cascades can approximate with a fast classifier
- Still imperfect: "What's your availability?" "Tuesday" (complete) vs "Tuesday…" (about to add more)

**Speaker notes**: Keep short — it's a horizon slide. Good final-writeup topic for interested students.

### Slide 8 — Barge-In: When the User Interrupts the Agent
- Barge-in = user starts talking while the agent is speaking; natural conversations are full of it
- Required response, in order: (1) detect user speech, (2) stop playback *immediately* — flush every buffer between you and the speaker, (3) cancel/ignore the rest of the model's in-flight response, (4) start listening as a new turn
- Latency target: agent should go silent within ~100–300 ms of the interruption or it feels like being talked over
- The flush must reach all buffers: your server-side queue *and* the provider/browser-side playout buffer (the `clear` message from week 2)

**Speaker notes**: Walk through the buffer chain on the week-2 pipeline diagram: model → server buffer → WebSocket → provider buffer → speaker. Missing any one flush means the agent "keeps talking" after being interrupted. In the realtime-API world this maps to concrete events: the model sends `input_audio_buffer.speech_started` (VAD heard the user), and your server reacts by flushing its queue and sending the provider/browser a `clear` message. That two-line reaction *is* barge-in. This is M5 material, introduced now because it motivates the next slide.

### Slide 9 — The Echo Problem: Your Agent Hears Itself
- On speakerphones and bad lines, the agent's own voice returns through the mic
- Naive barge-in then triggers on the agent's own speech → agent interrupts itself, forever
- Fix 1: **AEC** (week 2) — subtract the known playback signal from the input
- Fix 2: **state gating** — track an `agent_is_speaking` flag and require stronger evidence (higher VAD confidence, longer duration) to accept barge-in while it's set
- Production systems use both

**Speaker notes**: The self-interrupting agent is a hilarious and real failure mode — if you have a war story, tell it here. The state-gating idea generalizes: turn-taking logic is a small state machine (agent speaking / user speaking / both / neither), and bugs are usually missing transitions.

### Slide 10 — Don't Stream Silence
- Between turns, the mic still produces frames — of silence
- Streaming them anyway: wastes bandwidth and model quota, and can confuse endpointing
- Pattern: VAD-gated streaming — only forward audio to the model while (probable) speech is active, plus prefix padding so first syllables survive
- Bonus: silence trimming also keeps long calls inside model context/session limits

**Speaker notes**: Simple idea, real money: real-time model sessions bill and buffer on audio streamed. A 10-minute call is mostly silence.

### Slide 11 — The Turn-Taking State Machine
- Four states: IDLE (nobody speaking), USER_SPEAKING, AGENT_SPEAKING, INTERRUPTED
- Transitions labeled with the events that cause them (VAD onset/offset, playback start/finish, barge-in)
- Every event handler in your code should be expressible as one of these transitions
- "If you can't place a bug on this diagram, you don't understand it yet"

**Speaker notes**: Build the diagram live on the board, transition by transition, asking the class what should happen in each case. This becomes their M3/M5 design doc.

### Slide 12 — Milestone 3: "Listener"
- **Drop the button.** Run `webrtcvad` (or Silero) on the inbound 20 ms frames; your VAD + endpointing logic now decides when a turn starts and ends
- On detected end-of-turn: send the trimmed utterance (speech only, plus prefix padding) through the cascade automatically — STT → Grok → TTS
- Log turn boundaries live: `[SPEECH START]` / `[SPEECH END after 3.2 s → sending to Grok]`
- Definition of done: a **hands-free multi-turn conversation** — the TA talks, pauses mid-sentence without losing the turn, stops, and Grok answers; no keyboard, no button
- Stretch: two-tier VAD (webrtcvad gate + Silero confirm); tune and report your endpoint silence threshold and why you chose it

**Speaker notes**: This is the week the project starts feeling like magic — the button was the last piece of manual turn-taking, and removing it is the whole lecture made real. Grading emphasizes boundary *accuracy*: mid-sentence pauses under their chosen threshold must not split the turn, and background noise must not trigger Grok calls (each false trigger costs them money — mention that; it lands).

### Slide 13 — Homework & Reading
- M3 due before week 4
- Conceptual question: "Your agent keeps responding before users finish reading out their phone number. Which knobs do you turn, and what's the cost of each?"
- Conceptual question: "Describe the buffer-flush chain for barge-in in your own project's architecture."
- Optional: Silero VAD README; a paper/blog on conversational turn-taking gaps (e.g., Stivers et al. cross-linguistic turn-taking study — the 200 ms number)

## Live Demo Plan
1. Two failure recordings: too-eager vs too-patient agent
2. Silero VAD live speech-probability meter on the room mic
3. Build the turn-taking state machine on the whiteboard with class input

## Common Pitfalls
- Feeding VAD the wrong frame size (webrtcvad hard-requires 10/20/30 ms at supported rates)
- Forgetting prefix padding — first syllables get clipped and STT quality mysteriously drops
- Testing only in a quiet room — assign at least one noisy-environment test
