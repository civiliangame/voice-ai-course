# M1 — "Talkbox": a push-to-talk Grok agent

**Due before week 2.** Definition of done: the TA holds the button, asks your
agent a question, releases, and hears a sensible spoken answer. Graded on
behavior, not style.

## What's in the box

| File | Status | What it is |
|------|--------|------------|
| `server.py` | **you edit one function** | FastAPI server; `answer()` is your homework |
| `static/index.html` | provided | hold-to-talk page: records a clip, POSTs it, plays the reply, draws your latency bar |
| `hello_grok.py` | provided | the 3-line Grok completion from lecture (slide 13) |
| `.env.example` | copy to `.env` | your key + model names |
| `requirements.txt` | provided | fastapi, uvicorn, openai, python-dotenv |

## Setup & run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in XAI_API_KEY + model names (see docs.x.ai)
uvicorn server:app --reload --port 8000
```

Open **http://localhost:8000** — it must be `localhost`: browsers refuse mic
access on plain `http://` for any other host.

## The recommended path (from slide 14)

1. **Echo first (~10 min).** The scaffold already echoes your voice back.
   Run it, hold the button, say something, hear yourself. Now the entire
   audio path — mic → browser → server → browser → speaker — is proven,
   and any bug you hit from here on is in *your* code, not the plumbing.
2. **STT.** Replace the echo: send the clip to xAI speech-to-text, log the
   transcript. (Check the STT docs page for accepted audio formats — the
   browser sends compressed webm/Opus, or mp4 on Safari.)
3. **Grok.** Send the transcript + the provided short system prompt to chat
   completions.
4. **TTS.** Turn Grok's reply into audio and return it. Done — talk to it.

A commented skeleton of steps 2–4 is already inside `answer()`.

## Instrumentation is part of the milestone

Wrap each stage in `with timer.stage("stt"): ...` (etc.). The page then draws
a stacked latency bar per turn — that bar is the lecture's "latency budget"
slide, measured on your own machine.

**Deliverables:** your code, your measured STT / Grok / TTS milliseconds, and
one sentence on which stage surprised you.

**Conceptual question:** your Talkbox is push-to-talk. List everything that
has to become automatic before it's a phone call.

## Common failures (from lecture, in likelihood order)

- **Key/billing not set up** — run `python hello_grok.py` first; if that fails,
  nothing else matters.
- **STT rejects your audio** — you sent the browser's recording format without
  checking what the endpoint accepts. Read the docs page, don't guess.
- **No mic prompt** — you're not on `localhost` (or you previously denied
  permission; reset it in the browser's site settings).
- **It works but it's slow (2–4 s)** — correct! Three sequential blocking
  calls is this week's design. Don't optimize; weeks 2–4 do it properly and
  your timing logs are the before-picture.
