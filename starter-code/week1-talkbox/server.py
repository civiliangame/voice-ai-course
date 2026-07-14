"""M1 "Talkbox" — server scaffold.

You edit exactly ONE function in this file: `answer()` (search for "YOUR HOMEWORK").
Everything else is provided plumbing: an HTTP endpoint that receives the mic
clip from the browser, hands it to `answer()`, and ships the reply audio back
with per-stage timing headers the browser page knows how to display.

Run it:

    cp .env.example .env    # then fill in your key + model names
    uvicorn server:app --reload --port 8000

Then open http://localhost:8000 — `localhost` is exempt from the browser's
HTTPS-only microphone rule, which is why we serve on it (Lecture 1, pitfalls).

Architecture note (Slide 10): browser mic -> HTTP POST -> this process is the
training-wheels version of: caller -> telephony provider -> WebSocket -> your
server. Week 2 swaps the POST for a real continuous stream; the shape of the
server stays the same.
"""

from __future__ import annotations

import io  # noqa: F401  (used by the cascade you'll write in answer())
import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("talkbox")

app = FastAPI(title="M1 Talkbox")


# --------------------------------------------------------------------------
# Provided: xAI client + config helpers.
#
# The xAI API is OpenAI-SDK compatible (Slide 13): one base URL, one key,
# and the same client object does STT, chat, and TTS.
#
# Config is validated LAZILY so that echo mode works with zero setup:
# you only need a key and model names once you start writing the cascade.
# --------------------------------------------------------------------------

def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in. "
            f"Model names live at https://docs.x.ai — check the live models page, "
            f"don't guess (Slide 13)."
        )
    return value


def xai_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
        api_key=require_env("XAI_API_KEY"),
    )


# --------------------------------------------------------------------------
# Provided: per-stage stopwatch.
#
# Slide 14 makes instrumentation part of the milestone: "log the wall-clock
# time of each stage — STT, Grok, TTS — per request." Wrap each stage in
# `with timer.stage("stt"): ...` and this logs it AND sends it to the browser,
# which draws your personal version of Slide 5 (the latency budget).
# --------------------------------------------------------------------------

class StageTimer:
    def __init__(self) -> None:
        self.timings_ms: dict[str, int] = {}

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            ms = round((time.perf_counter() - t0) * 1000)
            self.timings_ms[name] = ms
            log.info("stage %-5s %5d ms", name, ms)


@dataclass
class AgentReply:
    """What `answer()` returns. transcript/reply_text are optional but showing
    them in the browser makes debugging dramatically easier — 'transcripts for
    free' is the cascade's superpower (Slide 6)."""

    audio: bytes
    mime: str
    transcript: str | None = None   # what STT heard
    reply_text: str | None = None   # what Grok said


# --------------------------------------------------------------------------
# YOUR HOMEWORK: implement the cascade inside answer().
#
# The recommended path (Slide 14):
#
#   Step 0 — ship the echo. The function below already echoes the clip back.
#            Run the server, hold the button, say something, hear yourself.
#            This proves mic -> server -> speaker before any API is involved
#            (~10 minutes, de-risks all the plumbing).
#
#   Step 1 — STT. Send the clip to xAI speech-to-text, get a transcript.
#
#   Step 2 — Grok. Send the transcript (plus a short system prompt) to
#            chat completions, get a reply.
#
#   Step 3 — TTS. Send the reply text to xAI text-to-speech, get audio,
#            return it instead of the echo.
#
# A skeleton of steps 1-3 is sketched in comments below. Notes:
#
#  * The three calls run SEQUENTIALLY and BLOCK. That is fine — encouraged,
#    even — this week (Lecture 1, pitfalls: "resist optimizing"). Weeks 2-4
#    stream and overlap these stages; week 5 makes blocking the event loop
#    a firing offense. First make it work, then make it fast — with data.
#
#  * The browser sends whatever compressed format MediaRecorder produced
#    (usually audio/webm with Opus; Safari sends audio/mp4). Check the STT
#    docs page for accepted formats before assuming it takes anything.
#
#  * Keep the system prompt SHORT and tell Grok it is speaking out loud:
#    answers get read by TTS, so two sentences beat two paragraphs.
# --------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a friendly voice assistant. Your answers are spoken aloud, "
    "so reply in one to three short conversational sentences, with no "
    "markdown, lists, or code."
)


async def answer(audio: bytes, mime: str, timer: StageTimer) -> AgentReply:
    # ---- Step 0: the echo (delete once your cascade works) -----------------
    return AgentReply(audio=audio, mime=mime)

    # ---- Steps 1-3: the cascade (uncomment, complete, and go) --------------
    # client = xai_client()
    #
    # with timer.stage("stt"):
    #     transcription = client.audio.transcriptions.create(
    #         model=require_env("STT_MODEL"),
    #         # The SDK wants a (filename, fileobj) tuple; the extension helps
    #         # the endpoint sniff the container format.
    #         file=(f"clip.{ext_for(mime)}", io.BytesIO(audio)),
    #     )
    #     transcript = transcription.text
    #
    # with timer.stage("llm"):
    #     chat = client.chat.completions.create(
    #         model=require_env("CHAT_MODEL"),
    #         messages=[
    #             {"role": "system", "content": SYSTEM_PROMPT},
    #             {"role": "user", "content": transcript},
    #         ],
    #     )
    #     reply_text = chat.choices[0].message.content
    #
    # with timer.stage("tts"):
    #     speech = client.audio.speech.create(
    #         model=require_env("TTS_MODEL"),
    #         voice=require_env("TTS_VOICE"),
    #         input=reply_text,
    #     )
    #     reply_audio = speech.content  # bytes; mp3 by default
    #
    # return AgentReply(
    #     audio=reply_audio,
    #     mime="audio/mpeg",
    #     transcript=transcript,
    #     reply_text=reply_text,
    # )


def ext_for(mime: str) -> str:
    """'audio/webm;codecs=opus' -> 'webm', 'audio/mp4' -> 'mp4', etc."""
    return mime.split(";")[0].split("/")[-1] or "webm"


# --------------------------------------------------------------------------
# Provided: the HTTP plumbing. You should read this (it's short) but you
# don't need to change it.
# --------------------------------------------------------------------------

@app.post("/answer")
async def answer_endpoint(request: Request) -> Response:
    audio = await request.body()
    mime = request.headers.get("content-type", "audio/webm")
    log.info("clip received: %d bytes, %s", len(audio), mime)

    timer = StageTimer()
    with timer.stage("total"):
        try:
            reply = await answer(audio, mime, timer)
        except Exception as exc:  # surface errors in the browser, not just the terminal
            log.exception("answer() failed")
            return Response(
                content=str(exc), status_code=500, media_type="text/plain"
            )

    # Timing + text ride back as headers so the page can display them.
    # json.dumps escapes non-ASCII, which HTTP headers require.
    headers = {"X-Timings": json.dumps(timer.timings_ms)}
    if reply.transcript is not None:
        headers["X-Transcript"] = json.dumps(reply.transcript)
    if reply.reply_text is not None:
        headers["X-Reply"] = json.dumps(reply.reply_text)

    return Response(content=reply.audio, media_type=reply.mime, headers=headers)


# Serve static/index.html at / — mounted last so /answer wins the route match.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
