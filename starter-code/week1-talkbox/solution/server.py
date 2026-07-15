"""M1 "Talkbox" — INSTRUCTOR REFERENCE SOLUTION. Do not distribute before the
milestone deadline.

Identical to the student scaffold except `answer()` is implemented (and the
static mount falls back to ../static so it runs from this directory as-is):

    uvicorn server:app --reload --port 8000

Grading reminder (syllabus): milestones are graded on behavior. If you can
talk to it and it answers sensibly out loud, it passes — then ask one random
"explain this function" question.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("talkbox")

app = FastAPI(title="M1 Talkbox (solution)")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in; "
            f"model names and voices live at https://docs.x.ai."
        )
    return value


def xai_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
        api_key=require_env("XAI_API_KEY"),
    )


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
    audio: bytes
    mime: str
    transcript: str | None = None
    reply_text: str | None = None


SYSTEM_PROMPT = (
    "You are a friendly voice assistant. Your answers are spoken aloud, "
    "so reply in one to three short conversational sentences, with no "
    "markdown, lists, or code."
)


async def answer(audio: bytes, mime: str, timer: StageTimer) -> AgentReply:
    """The week-1 cascade: STT -> Grok -> TTS, sequential and blocking.

    Only the Grok (chat) step is OpenAI-SDK compatible. xAI's speech-to-text
    and text-to-speech are NOT — they are native xAI REST endpoints
    (/v1/stt, /v1/tts), so we call them directly with `requests`. (The OpenAI
    `client.audio.*` methods would POST to /v1/audio/*, which xAI does not
    serve — that's a 404, not a formatting bug.)

    Blocking is deliberate this week (Lecture 1, pitfalls). When teaching,
    point at the three `with timer.stage(...)` blocks and note that weeks 2-4
    exist to overlap them, and week 5 to replace them with one WebSocket.
    (Note: `requests` is fully synchronous, so these calls block the event
    loop exactly like a blocking SDK call would — same week-5 lesson.)
    """
    api_key = require_env("XAI_API_KEY")
    client = xai_client()

    # Stage 1 — speech-to-text: compressed mic clip in, transcript out.
    # Native xAI endpoint: POST /v1/stt, multipart form-data, field "file"
    # (let requests set the multipart Content-Type; don't set it by hand).
    with timer.stage("stt"):
        resp = requests.post(
            "https://api.x.ai/v1/stt",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (f"clip.{ext_for(mime)}", audio, mime)},
        )
        resp.raise_for_status()
        transcript = resp.json()["text"]
    log.info("heard: %r", transcript)

    # Stage 2 — the brain: transcript in, reply out. Text is the interface
    # between stages (Slide 6) — which is why we can log it, and why the
    # cascade never hears the user's tone. This is the ONE OpenAI-SDK call:
    # same client object, just pointed at the xAI base_url.
    with timer.stage("llm"):
        chat = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "grok-4"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
        )
        reply_text = chat.choices[0].message.content or "Sorry, I have no answer."
    log.info("reply: %r", reply_text)

    # Stage 3 — text-to-speech: reply in, audio out (mp3 by default).
    # Native xAI endpoint: POST /v1/tts, JSON body. `language` is required;
    # "auto" lets xAI detect it from the reply text.
    with timer.stage("tts"):
        resp = requests.post(
            "https://api.x.ai/v1/tts",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "text": reply_text,
                "voice_id": require_env("TTS_VOICE"),
                "language": "auto",
            },
        )
        resp.raise_for_status()
        reply_audio = resp.content

    return AgentReply(
        audio=reply_audio,
        mime="audio/mpeg",
        transcript=transcript,
        reply_text=reply_text,
    )


def ext_for(mime: str) -> str:
    return mime.split(";")[0].split("/")[-1] or "webm"


@app.post("/answer")
async def answer_endpoint(request: Request) -> Response:
    audio = await request.body()
    mime = request.headers.get("content-type", "audio/webm")
    log.info("clip received: %d bytes, %s", len(audio), mime)

    timer = StageTimer()
    with timer.stage("total"):
        try:
            reply = await answer(audio, mime, timer)
        except Exception as exc:
            log.exception("answer() failed")
            return Response(content=str(exc), status_code=500, media_type="text/plain")

    headers = {"X-Timings": json.dumps(timer.timings_ms)}
    if reply.transcript is not None:
        headers["X-Transcript"] = json.dumps(reply.transcript)
    if reply.reply_text is not None:
        headers["X-Reply"] = json.dumps(reply.reply_text)

    return Response(content=reply.audio, media_type=reply.mime, headers=headers)


static_dir = "static" if os.path.isdir("static") else "../static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
