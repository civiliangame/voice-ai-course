# Week 6 — Production, the Provider Landscape & Demo Day

**Duration**: 90 min (≈45 min lecture + ≈45 min demos) · **Milestone**: Final demos + writeup

## Objectives

Students connect their project to the real world: actual phone lines, the multi-provider landscape (now including Gemini Live), evaluation, cost, and compliance. Then they demo.

## Slide-by-Slide (Lecture Half)

### Slide 1 — Title: "From Demo to Deployment"
- "Your agent works on your laptop. Today: what stands between that and a phone number real people call."

**Speaker notes**: Keep energy high and the lecture tight — the class wants to demo. Every slide here is a pointer into a rabbit hole, not the rabbit hole.

### Slide 2 — Putting It on a Real Phone Line
- Telephony providers (Telnyx, Twilio): rent a number, receive a webhook when it's called, answer with a command that starts a **bidirectional media stream** — a WebSocket of base64 µ-law, exactly like week 2 promised
- Reference architecture (provided): phone → Telnyx webhook → your server answers + starts media stream → server bridges Telnyx WS ↔ xAI Voice Agent WS
- With `audio/pcmu` on the xAI side: the bridge is nearly a pure relay — µ-law passes through untranscoded; barge-in is `speech_started` → Telnyx `clear`
- Call control beyond audio: transfer to a human, hang up, send SMS follow-ups mid-call

**Speaker notes**: Show the reference bridge diagram (phone → carrier → webhook/media-stream → xAI) and let it sink in that the whole bridge is a few hundred lines of Python. Students who did the stretch goal can attest. This is also the moment to say: everything browser-based they built maps 1:1 onto this — that was the design of the course, not an accident.

### Slide 3 — One Brain, Many Channels
- Real products answer the phone *and* the texts *and* the email — often mid-conversation across channels
- Architecture: domain logic (prompts, tools, business rules) in one place; thin channel adapters for voice/SMS/email transport
- Voice is realtime speech-to-speech; text channels use standard chat completions — same tools, same persona, different wire
- State lives in the database keyed by *person*, not by channel: the caller who texted yesterday is the same tenant

**Speaker notes**: Property-management example: tenant calls about a leak, agent schedules a plumber, confirmation goes by SMS, the survey next day by email — one conversation, three transports. This is why week 4 insisted on keeping transport out of business logic.

### Slide 4 — The Provider Landscape: Gemini Live & OpenAI Realtime
- Same concept, three vendors — now that you know xAI's version, the others are a diff, not a new subject:
- **Google Gemini Live API**: bidirectional streaming over Google's ADK/GenAI SDKs; VAD knobs are start/end-of-speech *sensitivity* + prefix padding + silence duration (week 3 names, Google spelling); strong tool calling; context-window compression built in for long sessions; regional endpoints matter
- **OpenAI Realtime API**: the protocol xAI's Voice Agent API is compatible with — your M5 event handling is ~90% portable by changing the URL
- Differences that actually matter when choosing: voice quality/latency, tool ecosystems (xAI ships server-side web/X search; Google integrates its stack), session limits & resumption, price, and concurrent-session quotas — **quota is the real production ceiling, ask early**
- Portability lesson: keep your event handling thin and your business logic provider-agnostic; you *will* switch or dual-source

**Speaker notes**: This is the promised "Gemini later" — teach it as a comparative, mapping every Gemini Live concept back to the xAI feature students already used (session config ↔ session.update; sensitivity knobs ↔ turn_detection; ADK tools ↔ function schemas). If time allows, show a Gemini Live snippet next to the equivalent xAI `session.update` side by side. Emphasize the quota point as the non-obvious production lesson: teams plan capacity around CPUs and discover the ceiling is concurrent model sessions.

### Slide 5 — Evaluating a Voice Agent
- "It sounded fine to me" doesn't scale — you need numbers
- Conversation metrics: task completion rate, handoff rate, latency percentiles (end-of-user-speech → first audio), interruption/barge-in frequency, call duration
- Transcript review: sample calls weekly; LLM-as-judge for rubric scoring at scale (did it confirm the address? did it invent a price?)
- Regression evals: replay scripted personas against every prompt/model change — treat prompts like code, with tests
- The audio layer needs evals too: word error rate on *your* domain vocabulary, VAD behavior in noise

**Speaker notes**: The eval-suite-as-CI idea is how serious teams operate: synthetic personas (the slow talker, the topic-changer, the mumbler) run against every change before it ships. Great final-writeup topic.

### Slide 6 — Cost of a Voice Minute
- Stack the meters: telephony per-minute + realtime model session time (or STT+LLM+TTS separately in a cascade) + infrastructure
- Cascade vs native is also a *cost* choice, and the answer changes with volume and call length
- Silence is money: week 3's VAD-gating and idle timeouts directly cut the bill
- Order-of-magnitude exercise in class: estimate cost per 5-minute call for both architectures (use current published prices — they change; the *method* is the lesson)

**Speaker notes**: Do the estimate live with the class supplying numbers from the pricing pages. The durable lesson is the method (enumerate meters, multiply by minutes) — printed numbers will be stale within a quarter.

### Slide 7 — Compliance & Safety (The Short, Serious Slide)
- Call recording: consent laws vary by jurisdiction (some require all-party consent) — disclose and get consent, always
- AI disclosure: growing legal requirements to identify as an AI; it's also just good product manners — use scripted delivery (`force_message`) for lines that must be exact
- PII: transcripts are full of names, addresses, payment details — encrypt, retain minimally, redact logs
- Quiet hours for outbound: nobody wants a robot call at 6 am; timezone-aware scheduling is a feature, not polish
- Vulnerable callers: emergencies ("I smell gas") need hard-coded escalation paths that bypass the LLM entirely

**Speaker notes**: The gas-leak example earns its place: routing rules for emergencies must be deterministic system code, not model judgment — the week-4 "prompt is a request, system enforces" principle at its highest stakes.

### Slide 8 — Scaling (One Slide of Systems Reality)
- One asyncio process handles a surprising number of concurrent calls *if* nothing blocks (week 5) — audio work in C extensions, I/O all async
- Beyond one process: in-memory session state is the enemy — externalize to Redis/DB before adding workers, and mind WebSocket stickiness across workers
- Cloud-run-style horizontal scaling often sidesteps multi-worker complexity: one process per instance, scale instances
- And again: the ceiling is usually provider session quota, not your CPUs

**Speaker notes**: One slide only — it's a distributed-systems course invitation, not content to cover. The "externalize state before adding workers" ordering is the takeaway.

### Slide 9 — Where the Field Is Going
- Full-duplex models (listening *while* speaking — real overlap, backchannels)
- Semantic endpointing as the default; VAD as a hint, not the decider
- Emotional/expressive TTS and custom voice cloning (already shipping: xAI custom voices)
- Speech-native reasoning: models that think in audio without a text bottleneck
- On-device/edge voice for latency and privacy

**Speaker notes**: End the lecture arc where week 1 began: the 200 ms human turn gap. Everything on this slide is the industry clawing its way toward conversation that feels human. Your students now know exactly which parts are hard and why.

### Slide 10 — Demo Day Format
- 5 minutes per student/pair: 30-second pitch (who is your agent, for whom?) → live conversation including **one tool call** and **one barge-in** → your worst failure during development and how you fixed it
- Grading rubric on screen: works live (40%), turn-taking quality (20%), tool integration (20%), the failure story (20%)
- Audience role: each student writes one "I'd steal that" note about someone else's agent

**Speaker notes**: The "worst failure" segment is deliberately weighted — it produces the best learning moments and the best stories. Have a backup plan for demo-day Wi-Fi (hotspot, and allow a recorded backup video with live Q&A).

## Demo Day (Second Half)

Run demos. Keep a visible shot clock. Collect the "I'd steal that" notes and read a few aloud at the end.

## Final Writeup (due 1 week after demo day)
2–3 pages: your architecture (diagram required), two tradeoffs you made and why, the failure that taught you the most, and what you'd build next with two more weeks.

## Common Pitfalls (for you, the instructor)
- Letting the lecture half run long — cut slides 8–9 before cutting demo time
- Live-demo dependencies: have recordings of every demo as backup
- Cost numbers on slides go stale — pull pricing pages live instead of baking numbers into the deck
