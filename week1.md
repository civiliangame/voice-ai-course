# Week 1 — The Anatomy of a Voice Agent (+ xAI Quickstart)

**Duration**: 75–90 min · **Milestone**: M1 "Talkbox" — a push-to-talk Grok agent, built as homework

## Objectives

Students leave understanding the two dominant voice-agent architectures (cascade vs. native speech-to-speech), why latency dominates every design decision, and how audio physically travels from a caller to a model and back. They also leave with a working xAI API key and everything needed to stitch STT → Grok → TTS together **this week** — the course is hands-on with Grok from day one.

## Slide-by-Slide

### Slide 1 — Title: "Voice Is the Hardest UI"
- Course title, your name, week 1 of 6
- One-line hook: "By week 6 you'll have built an AI you can talk to — and interrupt."

**Speaker notes**: Open with a live 30-second demo of the *finished* project (or a production agent if you can show one safely). Let them hear a natural back-and-forth including an interruption. Then say: "Everything you just heard is a lie held together by buffering. Let's take it apart."

### Slide 2 — What You'll Build
- The milestone ladder: Talkbox → Plumber → Listener → Brain → Survivor → Demo Day
- **This week's homework: your agent already talks** — mic clip → xAI STT → Grok → xAI TTS → spoken answer
- Each later week upgrades that same agent: real streaming, hands-free turns, tools, native speech-to-speech
- "Graded on behavior, not style: if the TA can talk to it, you pass"

**Speaker notes**: Emphasize the inversion: most courses make you build plumbing for a month before anything interesting happens. Here the agent speaks in week 1, and every week after answers the question "why does the naive version fall short?"

### Slide 3 — Where Voice Agents Live Today
- Call centers & customer support (the biggest deployment)
- Vertical agents: property management, healthcare scheduling, restaurants, logistics
- Assistants: in-car, smart speakers, phone assistants
- Key stat framing: most business phone calls are routine and structured — perfect automation targets

**Speaker notes**: Use a real vertical you know well (e.g., property management: leasing inquiries, maintenance requests) as the running example for the whole course. A tenant calling about a broken heater at 2am is a great recurring scenario.

### Slide 4 — Why Voice Is Hard (vs. a Chatbot)
- **No undo**: spoken words can't be edited after the fact; a chatbot response can render progressively
- **Latency is felt viscerally**: 3 seconds of silence on a phone call feels broken; 3 seconds for a chat reply feels normal
- **Ambiguity**: no punctuation, homophones, accents, background noise, crosstalk
- **Turn-taking**: humans interrupt, backchannel ("uh-huh"), and pause mid-thought

**Speaker notes**: The chatbot mental model actively misleads people building voice. Everything downstream (this whole course) exists because of these four bullets.

### Slide 5 — The Latency Budget
- Human conversational gap: ~200–300 ms between turns (linguistics research)
- Practical target for "feels responsive": under ~1 second mouth-to-ear
- Budget breakdown diagram: network transit + audio buffering + speech detection + model inference + speech synthesis + playback buffering
- Every component in this course is fighting for milliseconds

**Speaker notes**: Draw the budget as a stacked bar. Point out that endpointing (deciding the user finished speaking) often costs more than model inference — you literally must wait through silence to be sure they're done. That tradeoff gets its own lecture (week 3).

### Slide 6 — Architecture #1: The Cascade
- Diagram: Mic → **STT** (speech-to-text) → **LLM** → **TTS** (text-to-speech) → Speaker
- Each stage is a separate model/service; text is the interface between stages
- Pros: modular, debuggable, swap any component, transcripts for free
- Cons: latency adds up per stage; loses paralinguistic info (tone, emotion, hesitation)

**Speaker notes**: This is what students build in week 4. Stress the "text as interface" point — it's why cascades are debuggable and why they're lossy.

### Slide 7 — Architecture #2: Native Speech-to-Speech
- Diagram: Mic → **one multimodal model** (audio in, audio out) → Speaker
- Examples: **xAI Grok Voice Agent API** (our platform, weeks 5–6), Google Gemini Live API, OpenAI Realtime API
- Bidirectional WebSocket session: you stream audio in continuously; it streams audio out as events
- The OpenAI Realtime wire protocol has become a de facto standard — xAI's Voice Agent API is compatible with it, so most client libraries work by changing the WebSocket URL
- Pros: lower latency, hears tone/hesitation, natural prosody out
- Cons: less controllable, harder to debug, session state lives inside the provider, quotas on concurrent sessions

**Speaker notes**: Production systems increasingly use these for the voice channel while keeping text models for SMS/email. Mention that these APIs still emit text transcripts of both sides — you always want those for logging and debugging. The protocol-compatibility point matters pedagogically: learn the event model once (week 5), and you can drive xAI, OpenAI, and (with small differences) Gemini.

### Slide 8 — Cascade vs. Native: When to Use Which
- Table: latency / controllability / debuggability / cost / voice quality / tool-calling maturity
- Rule of thumb: cascade when you need tight control and auditability; native when conversational feel is the product
- Hybrid reality: same "brain" logic (tools, prompts, business rules) should work behind either

**Speaker notes**: Foreshadow the multi-channel idea from week 6: a well-designed agent core doesn't care if it's talking through voice, SMS, or email.

### Slide 9 — How Audio Actually Travels: The Phone Path
- Caller → PSTN/carrier → telephony provider (Twilio/Telnyx) → **WebSocket media stream** to your server
- Audio arrives as small JSON messages: base64-encoded 8 kHz µ-law chunks, ~20 ms each
- Your server sends audio back the same way
- Control events ride the same socket: call started, call ended, marks

**Speaker notes**: Students are often surprised the "phone call" reaches their Python process as JSON-over-WebSocket at 50 messages/second. Show one real (redacted) media message on screen. Week 2 explains every field.

### Slide 10 — How Audio Travels: The Browser Path (Our Project)
- Browser `getUserMedia` → Web Audio API → WebSocket → your Python server
- Same architecture as telephony, minus the carrier — which is why we use it
- Diagram mapping browser path onto phone path 1:1

**Speaker notes**: Explicitly draw the correspondence: browser mic ≈ caller, WebSocket ≈ provider media stream. Everything they build transfers to real telephony almost unchanged.

### Slide 11 — A Production Topology
- Full diagram (generic): Telephony provider → WebSocket handler → audio preprocessing (decode, resample, denoise) → VAD/turn detection → model session (streaming) → response audio → paced sender → provider
- Sidecar concerns around the box: transcripts/logging, database (CRM, work orders), schedulers, human handoff
- "This diagram is the table of contents for this course"

**Speaker notes**: Walk the diagram left to right and tag each block with its week number. This is the single most important slide of the lecture — students should photograph it.

### Slide 12 — Everything Is a Stream
- Mental model shift: no request/response; long-lived concurrent streams
- One phone call = many concurrent tasks: receive loop, send loop, audio processor, model event consumer, health monitor
- Python's answer: `asyncio` — one event loop, cooperative multitasking
- Golden rule preview: **never block the event loop** (week 5)

**Speaker notes**: Quick asyncio refresher poll — who has used it? Reassure: the project scaffolding handles the boilerplate; the concepts are what matter.

### Slide 13 — Your Toolkit: The xAI API in 90 Seconds
- One key, one base URL, one docs site: `https://api.x.ai/v1`, Bearer auth, key from **console.x.ai**
- OpenAI-SDK compatible: `OpenAI(base_url="https://api.x.ai/v1", api_key=...)` — the `openai` Python package works as-is
- The three calls you need this week: **speech-to-text** (audio in, transcript out), **chat completions with Grok** (transcript in, reply out), **text-to-speech** (reply in, audio out)
- Live now: everyone creates a key and runs a 3-line Grok completion before leaving

**Speaker notes**: Do the key setup *in class* — key/billing problems are the #1 homework blocker, and finding them now instead of Sunday night is the whole point of this slide. Have the 3-line snippet on screen and in the scaffold README. Current flagship text models are the grok-4 family; check the models page live rather than trusting slides.

### Slide 14 — Milestone 1: "Talkbox"
- Ship: a push-to-talk Grok agent — hold the button, ask a question, release, hear Grok answer out loud
- Provided scaffold: browser page (hold-to-record button, sends the clip to your server, plays the response); server skeleton with an `answer(audio)` stub
- You write the cascade: clip → xAI STT → transcript + short system prompt → Grok → reply → xAI TTS → audio back
- Recommended path: make the stub *echo* the clip first (plumbing test, ~10 min), then replace the echo with the three xAI calls
- **Instrument it**: log the wall-clock time of each stage — STT, Grok, TTS — per request

**Speaker notes**: The echo-first step de-risks the audio plumbing before students touch the API. The per-stage timing requirement is the pedagogical core: their own logs become slide 5 (the latency budget) made personal, and week 4's streaming work will be motivated by numbers they measured themselves.

### Slide 15 — Homework & Reading
- M1 Talkbox due before week 2 — definition of done: the TA asks it a question and hears a sensible spoken answer
- Deliverable alongside the code: your measured latency breakdown (STT / Grok / TTS in ms) and one sentence on which stage surprised you
- Conceptual question: "Your Talkbox is push-to-talk. List everything that has to become automatic before it's a phone call." (This is the course syllabus, rediscovered by the student — collect answers, revisit in week 6)
- Optional reading: telephony media-stream docs of one provider (Twilio or Telnyx); the xAI Voice Agent API overview page (docs.x.ai — just skim the event names; we cover it deeply in week 5)

## Live Demo Plan
1. Finished project demo (open of class, 30 s)
2. Show a raw telephony media-stream JSON message and decode its base64 payload live in a Python REPL — "this is a phone call"
3. xAI key setup + 3-line Grok completion, everyone follows along (slide 13)

## Common Pitfalls to Warn About
- API key not created / billing not set up — that's why it happens in class
- Sending the browser's default compressed recording format to STT without checking what the endpoint accepts — read the STT docs page, don't guess
- Mic permission issues on browsers over `http://` — serve on `localhost` (exempt) or use HTTPS
- Blocking on all three API calls sequentially is *fine this week* — resist optimizing; weeks 2–4 do it properly
