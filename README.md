# Building Real-Time Voice AI Agents

A 6-week university course (Samsung University, CS Dept) on building production-grade
voice AI agents — from µ-law audio frames to a talking, tool-using, interruptible
agent on the xAI Grok voice stack.

## Contents

| File | What it is |
|---|---|
| [SYLLABUS.md](SYLLABUS.md) | Course overview, milestones, grading |
| [slides.html](slides.html) | Full lecture slide deck (open in a browser; `→`/`←` to navigate, `N` for speaker notes, `T` for dark mode, `Esc` for contents) |
| [course-overview.html](course-overview.html) | One-page course overview |
| [week1.md](week1.md) – [week6.md](week6.md) | Detailed lecture notes per week |
| [starter-code/](starter-code/) | Milestone scaffolds (Week 1: Talkbox — push-to-talk STT → Grok → TTS agent) |

## The six milestones

1. **M1 Talkbox** — push-to-talk Grok agent: STT → Grok → TTS
2. **M2 Plumber** — continuous streaming + a simulated phone line
3. **M3 Listener** — VAD-driven, hands-free turn-taking
4. **M4 Brain** — tool calling, persona, sentence-streamed TTS
5. **M5 Survivor** — native speech-to-speech, barge-in, watchdog
6. **Demo day** — live conversation with one tool call and one barge-in

## Getting started

See [starter-code/week1-talkbox/README.md](starter-code/week1-talkbox/README.md).
You'll need an API key from [console.x.ai](https://console.x.ai) — copy
`.env.example` to `.env` and fill it in. Never commit a real key.
