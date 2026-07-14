# Building Real-Time Voice AI Agents

**A 6-week lecture course · Samsung University · CS Department**

## Course Description

Voice is the oldest human interface and the hardest one to build software for. This course teaches you how modern real-time voice AI agents actually work — not the demo-video version, but the production version: audio codecs and resampling, voice activity detection and turn-taking, streaming LLM integration with tool calling, and the reliability engineering that keeps a live phone call alive when everything wants to fail mid-sentence.

The course is grounded in real production systems (telephony-connected AI agents handling live phone calls at scale). Our primary platform is the **xAI API**, and you are hands-on with Grok from day one: your very first homework stitches speech-to-text → Grok → text-to-speech into an agent that answers you out loud. Every subsequent week upgrades that same agent — real streaming audio, hands-free turn detection, tools and personas, then native speech-to-speech with the **Grok Voice Agent API** (real-time, over WebSocket). In the final week we survey the wider provider landscape — Google's Gemini Live API and OpenAI's Realtime API — and you'll see that everything you learned transfers, because the concepts (and increasingly the wire protocols) are shared.

Each week combines a 60–90 minute lecture with a build-along project milestone: by week 6 you will have a working voice agent you built yourself — one that listens, thinks, talks, uses tools, and survives interruptions.

## Prerequisites

- Proficiency in Python (you should be comfortable reading and writing non-trivial Python)
- Basic familiarity with HTTP and WebSockets (we review what's needed)
- Helpful but not required: `asyncio`, basic signal processing
- A laptop with a microphone and a modern browser

## Learning Objectives

By the end of the course you will be able to:

1. Explain the end-to-end architecture of a real-time voice agent, from microphone (or phone line) to model and back.
2. Manipulate raw audio in Python: PCM, µ-law, sample rates, framing, and resampling.
3. Implement voice activity detection and turn-taking logic, including barge-in (user interruptions).
4. Build both dominant architectures on the xAI API: a cascade (STT → Grok → TTS) and a native speech-to-speech agent (Grok Voice Agent API) with function calling.
5. Design for real-time reliability: fixed-rate audio delivery, watchdogs, reconnection, and session resumption.
6. Compare voice AI providers (xAI, Google Gemini Live, OpenAI Realtime) and reason about production concerns: evaluation, cost, compliance, and scaling.

## Format

- **6 weekly lectures**, 60–90 minutes each, slides + live demos
- **Build-along project**: weekly milestones, each building on the last
- **Weekly homework**: the project milestone plus 1–2 short conceptual questions

## The Build-Along Project: "Talkbox → Agent"

You will build a browser-based voice agent in Python. It talks — via Grok — from week 1, and gains a new capability every week:

| Week | Milestone | What it does |
|------|-----------|--------------|
| 1 | **M1 — Talkbox** | Push-to-talk Grok agent: mic clip → xAI STT → Grok → xAI TTS → spoken answer |
| 2 | **M2 — Plumber** | Real-time plumbing: continuous audio streaming, resampling, µ-law round-trip (simulated phone line), buffered playback |
| 3 | **M3 — Listener** | Drop the button: VAD detects your turns automatically — a hands-free conversation |
| 4 | **M4 — Brain** | Function calling (one real tool), a persona, and sentence-streamed TTS that cuts latency in half |
| 5 | **M5 — Survivor** | Go native: Grok Voice Agent API (speech-to-speech) with barge-in, a watchdog, and reconnection |
| 6 | **Demo Day** | Polish, a personality, and a 5-minute live demo |

We use the browser microphone instead of a real phone line so nobody needs a telephony account — but the server-side architecture mirrors production telephony systems (the Voice Agent API even speaks G.711 µ-law natively, the phone network's codec), and an optional stretch goal connects your agent to a real phone number.

**Stretch goals** (optional, any week): connect a Telnyx/Twilio phone number (a reference bridge architecture is provided in class); port your agent to Google's Gemini Live API and compare; add a second tool; use `force_message` for scripted compliance lines; add neural noise suppression; try a custom voice.

## Weekly Schedule

| Week | Lecture | Project Milestone |
|------|---------|-------------------|
| 1 | The Anatomy of a Voice Agent (+ xAI quickstart) | M1 — Talkbox (push-to-talk Grok cascade) |
| 2 | Audio for Engineers Who Skipped DSP | M2 — Plumber (streaming audio pipeline) |
| 3 | Turn-Taking: VAD, Endpointing, and Interruptions | M3 — Listener (hands-free turns) |
| 4 | The Brain: Grok, Tools, and Prompting for Speech | M4 — Brain (tools + streaming) |
| 5 | Going Native: The Voice Agent API & Real-Time Reliability | M5 — Survivor (speech-to-speech) |
| 6 | Production, the Provider Landscape (Gemini Live) & Demo Day | Final demos |

## Grading

| Component | Weight |
|-----------|--------|
| Project milestones M1–M5 (8% each) | 40% |
| Final demo (working agent, live) | 30% |
| Final writeup (2–3 pages: architecture, tradeoffs, failure modes you hit) | 15% |
| Participation & homework questions | 15% |

Milestones are graded on **working behavior**, not code style: if the TA can talk to it and it does what the milestone says, you pass the milestone.

## Tools & Accounts Needed

- Python 3.11+, `pip`, a virtualenv
- Packages (installed as needed): `fastapi`, `uvicorn`, `websockets`, `numpy`, `soxr`, `webrtcvad`, `silero-vad` (via `torch`), `openai` (SDK — used against the xAI endpoint)
- An **xAI API key** from console.x.ai — required for the week-1 homework, so it's set up in the first lecture. The xAI API is OpenAI-SDK-compatible: point the SDK at `https://api.x.ai/v1`
- A Google AI Studio key (week 6 Gemini Live comparison, optional)
- No telephony account required (optional for the stretch goal)

## Policies

- **Collaboration**: discuss freely, write your own code. Milestones are individual.
- **AI assistants**: allowed and encouraged — you're taking a class about them. But you must be able to explain every line you submit; a random "explain this function" question accompanies each milestone check.
- **Late work**: each milestone can be turned in up to 1 week late at −25%; the project is cumulative, so falling behind hurts more than the penalty does.
