# Starter Code — Building Real-Time Voice AI Agents

This directory holds the build-along project scaffolds, one folder per milestone:

| Week | Folder | Milestone |
|------|--------|-----------|
| 1 | `week1-talkbox/` | M1 — push-to-talk Grok cascade |
| 2 | `week2-dispatcher/` | M2 — Dispatcher (tools + worker) |
| 3 | *(added in week 3)* | M3 — Listener |
| 4 | *(added in week 4)* | M4 — Brain |
| 5 | *(added in week 5)* | M5 — Survivor |

Each milestone folder contains a working scaffold, a `WALKTHROUGH.md` for the
instructor (slide-by-slide teaching notes for the code), and a `solution/`
subfolder — **instructor reference only**, don't distribute to students before
the milestone deadline.

## One-time environment setup (done live in Lecture 1, Slide 13)

```bash
# 1. Python 3.11+ in a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 2. Install this week's dependencies
pip install -r week1-talkbox/requirements.txt

# 3. Get an xAI API key from https://console.x.ai
#    (create the key AND confirm billing/credits — this is the #1 homework blocker)
export XAI_API_KEY="xai-..."

# 4. Prove the key works before leaving class:
python week1-talkbox/hello_grok.py
```

If step 4 prints a sentence from Grok, you are unblocked for the homework.
Everything else this week is plumbing around that call.

## The server framework: FastAPI, every week

All five milestone servers are **FastAPI** apps started with
`uvicorn server:app --reload`. The framework choice is part of the curriculum:

- **Week 1:** one HTTP endpoint + `StaticFiles`. You can read the entire server
  in a minute — that's the point.
- **Week 2:** the same HTTP app grows a tool belt, conversation memory, and
  a second process (the ticket worker) beside it.
- **Weeks 3–5:** the HTTP POST becomes a FastAPI **WebSocket** route
  (`@app.websocket(...)`) carrying a continuous audio stream, which mirrors
  1:1 how a telephony provider delivers a phone call to your backend.
- **Why async matters:** FastAPI runs on asyncio. A voice server is many
  concurrent long-lived streams, and one blocking call stutters *every* call
  in the process — that's the week-5 golden rule, and FastAPI is where you
  practice it.

If you're new to FastAPI: `app = FastAPI()` creates the app, decorators like
`@app.post("/answer")` register handlers, and uvicorn is the ASGI server that
runs it all. That's all you need for week 1.

## The one fact to remember about the xAI API

**Grok (chat) is OpenAI-SDK compatible** — one base URL, one key:

```python
from openai import OpenAI
client = OpenAI(base_url="https://api.x.ai/v1", api_key=os.environ["XAI_API_KEY"])
reply = client.chat.completions.create(model="grok-4", messages=[...])
```

**But xAI's audio is NOT OpenAI-SDK compatible.** Speech-to-text and
text-to-speech are native xAI REST endpoints — the OpenAI `client.audio.*`
methods hit `/v1/audio/*`, which xAI does not serve (you'll get a 404). Call
them directly with `requests`:

- **STT:** `POST https://api.x.ai/v1/stt` — multipart form-data, field `file`;
  transcript comes back as `resp.json()["text"]`.
- **TTS:** `POST https://api.x.ai/v1/tts` — JSON `{text, voice_id, language}`;
  reply is raw audio bytes (mp3 by default) in `resp.content`.

So week 1 uses two clients: the OpenAI SDK for Grok, plain `requests` for
STT/TTS. Endpoints, voices, and model names change faster than course
materials: **always check https://docs.x.ai before hardcoding anything**
(Slide 13's speaker notes say the same thing).
