# Week 4 — The Brain: Grok, Tools, and Prompting for Speech

**Duration**: 75–90 min · **Milestone**: M4 "Brain" (xAI cascade)

## Objectives

Students already have a talking, hands-free cascade — this week it gets *smart*: function calling against real data, a persona, and streaming that cuts perceived latency in half. Plus the underrated part: how prompting for the *ear* differs from prompting for the *eye*.

## Slide-by-Slide

### Slide 1 — Title: "The Brain"
- "Your agent talks. This week it gets hands, a name, and half its latency back."

**Speaker notes**: Demo the finished M4 up front: a hands-free question, a Grok answer, then trigger the tool ("what's the status of my maintenance request?") so they see a tool call happen live in the server logs.

### Slide 2 — The Cascade You've Been Building
- Three weeks in: mic → VAD/endpointing → **xAI STT** → **Grok** → **xAI TTS** → buffered playout — you built every box
- Text is the interface between every stage → log it all; your transcript is your debugger
- The brain unit-tests without audio: type text in, read text out — the cascade's superpower

**Speaker notes**: A recap that doubles as a confidence moment — put the week-1 topology diagram back up and check off what they've built. The testability point is why production systems keep cascades around even when native speech-to-speech exists.

### Slide 3 — Where Your Milliseconds Went
- Pull up the class's M1 latency logs: STT + Grok + TTS, run *sequentially*, waiting for each to finish
- The worst offender isn't any single stage — it's waiting for the **whole** Grok reply before TTS can start
- Today's fixes: streaming (this lecture), and keeping tools fast (slide 6)
- Week 5 fixes the rest: one model, one socket, no text bottleneck

**Speaker notes**: Use real numbers students submitted with M1 — nothing motivates like their own logs. This slide turns the week-1 latency-budget theory into their measured reality and sets up the streaming slide as the payoff.

### Slide 4 — Streaming, or: Never Wait for the Whole Answer
- Non-streaming: user waits for the full completion before TTS can start — worst-case latency
- Streaming: tokens arrive as generated → chunk into sentences → TTS each sentence as it completes → playback starts after the *first sentence*, not the last
- Sentence-chunking heuristics: split on terminal punctuation, minimum length guard (don't TTS "Dr.")
- This one technique typically cuts perceived latency by more than half

**Speaker notes**: Draw the two timelines (sequential vs pipelined) — the visual makes it obvious. Note the subtlety: you're now managing a queue of TTS jobs whose audio must play in order. Concurrency arrives whether you invited it or not.

### Slide 5 — Function Calling: Giving the Brain Hands
- The mechanism: you describe functions (name, JSON-schema parameters, description); the model replies with "call this function with these arguments" instead of text; you execute and return the result; the model continues
- The docstring/description *is* the interface — the model decides when to call based purely on what you wrote
- Define tools from Python: signature + docstring → JSON schema (write it by hand once so the magic is understood)
- Grok supports parallel tool calls: the model may request several at once; return all results before continuing

**Speaker notes**: Emphasize the description-quality point with a live A/B: a vaguely-described tool the model never calls vs a precisely-described one it calls reliably. In production systems, tool descriptions get more editing attention than system prompts.

### Slide 6 — Tool Design for Voice Agents
- Return structured data, not prose: `{"status": "success", "appointment": "2026-07-21T14:00"}` — let the model verbalize it
- Errors are data, not exceptions: `{"status": "error", "message": "no availability that day"}` — the model can recover gracefully in speech ("that day's full — how about Tuesday?"); a raised exception kills the turn
- Keep tools fast (< ~1 s) or say something first: dead air during a slow tool call feels like a dropped call
- Idempotency matters: users repeat themselves; your `book_appointment` will get called twice

**Speaker notes**: The "errors are data" pattern is a production rule worth stating as law. The latency point previews week 5's `force_message`/filler techniques — on a phone, you must hold the floor while you work.

### Slide 7 — Prompting for the Ear, Not the Eye
- No markdown, no bullet lists, no headers — it all gets *read aloud, literally* ("asterisk asterisk important asterisk asterisk")
- Short sentences; one idea per sentence; front-load the answer
- Numbers, addresses, emails: write them the way they should be *spoken* ("two oh six, eight eight oh…") and confirm digit strings back to the user
- Set conversational persona in the system prompt: name, role, what it can/can't do, when to hand off to a human
- Explicit brevity instruction — LLMs default to essay length; phone turns should be 1–3 sentences

**Speaker notes**: Read a markdown-formatted LLM response out loud verbatim, asterisks and all — gets a laugh and makes the point permanently. Pronunciation edge cases (addresses, unit numbers, "St." = street or saint?) are a real production pain; the realtime APIs even ship pronunciation-replacement features for exactly this (week 5).

### Slide 8 — State and Memory
- Three layers of state: the current turn (in the prompt), the conversation (message history you maintain and resend), the world (your database — the only durable one)
- Rule: anything that must survive a dropped call goes in the database *via a tool*, not in conversation memory
- Long calls: context grows every turn → trim or summarize old turns; realtime APIs do context compression internally, cascades do it manually
- Load prior history at call start ("welcome back — are you calling about the leak from yesterday?") — this is just prepending messages

**Speaker notes**: The dropped-call framing makes state design concrete: a phone call can die at any second. What should the agent remember when the user calls back? That list = your database schema.

### Slide 9 — Multi-Agent Architectures
- One agent that does everything = one prompt that does nothing well
- Production pattern: a thin **triage/router agent** classifies intent, then hands off to a **domain specialist** (e.g., leasing questions vs. maintenance requests) with its own prompt, tools, and history
- Handoffs by channel: on voice, transfer the call or swap the session config; on text, persist the routing decision
- Channel adapters: the same domain brain should work over voice, SMS, and email — keep transport code out of business logic

**Speaker notes**: Use the property-management running example: "I want to see the 2-bedroom on Main St" vs "my heater is broken" are different worlds — different tools, different urgency, different prompts. Trying to serve both from one prompt degrades both.

### Slide 10 — Guardrails for a Live Phone Call
- The model speaks in real time to a real person — there's no human review between generation and delivery
- Prompt-level: forbidden topics, no invented facts about inventory/pricing (tools are the source of truth), always disclose being an AI when asked
- System-level: cap call duration, cap tool-call loops, profanity/PII filters on transcripts, human-handoff escape hatch always available
- Design stance: the prompt is a request; the *system* enforces the rules

**Speaker notes**: "The prompt is a request, the system enforces" is the takeaway sentence. Give an example: don't just tell the model to never quote a price — don't give it prices except through a tool that returns approved ones.

### Slide 11 — Milestone 4: "Brain"
- Implement **one tool** via Grok function calling and make it real enough to demo (e.g., `check_apartment_availability(bedrooms, move_in_month)` against a hardcoded dict), with conversation history across turns
- Prompt requirement: an agent persona with a name, a job, and spoken-style constraints (no markdown reaches TTS)
- Implement **sentence-streamed TTS**: stream Grok's reply, chunk into sentences, TTS each as it completes — first audio out before generation finishes
- Definition of done: hands-free 3+ turn conversation, one turn visibly triggers the tool, and your end-of-speech → first-audio latency is measurably below your M1 baseline
- Stretch: a second tool with parallel calls; "hold the floor" filler while a slow tool runs

**Speaker notes**: Streaming is core this week, not a stretch — students have carried their M1 latency numbers for three weeks and this is where they get to beat them. Publish a latency leaderboard (voluntary): end-of-user-speech → first audio out. Nothing motivates pipeline optimization like a scoreboard.

### Slide 12 — Homework & Reading
- M4 due before week 5
- Conceptual question: "Your tool takes 4 seconds. Describe two different techniques to keep the call feeling alive, and their tradeoffs."
- Conceptual question: "Why should `book_appointment` be idempotent in a voice context specifically?"
- Required skim: xAI Voice Agent API docs page (docs.x.ai → Voice) — read the event list; next week we use all of it
- Optional: xAI function-calling guide; a post on sentence-chunked TTS streaming

## Live Demo Plan
1. Finished M4 demo with visible tool call in logs
2. 3-line xAI API sanity check (students follow along with their own keys)
3. Read a markdown response aloud verbatim (the prompting-for-the-ear bit)
4. A/B of a vague vs precise tool description

## Common Pitfalls
- Out-of-order playback from the sentence-streamed TTS queue — audio must play in sentence order even when later chunks synthesize faster
- TTS-ing the raw markdown response — enforce spoken-style prompt early
- Blocking the event loop with a synchronous STT/LLM/TTS call — everything must be `await`ed or offloaded (full treatment next week)
- Sending the model the whole audio buffer instead of the VAD-trimmed utterance
