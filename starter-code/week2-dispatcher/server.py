"""M2 "Dispatcher" — server scaffold.

Week 1's homework — the STT -> Grok -> TTS cascade — is PROVIDED this week,
already wired to the native xAI endpoints. What's new, and what you build,
is the TOOL BELT (Lecture 2, Part 2):

    YOUR HOMEWORK 1 — declare the two tool schemas       (search: HOMEWORK 1)
    YOUR HOMEWORK 2 — implement the two tool functions   (search: HOMEWORK 2)
    YOUR HOMEWORK 3 — the tool-call loop inside think()  (search: HOMEWORK 3)

Out of the box this scaffold runs as week 1's Talkbox *with conversation
memory* — nothing to configure beyond last week's .env. That's your step 0:
prove the plumbing still works, then start on the tools.

Run it (plus the worker, in a second terminal — see worker.py):

    cp .env.example .env      # same values as week 1
    uvicorn server:app --reload --port 8000
    python worker.py          # terminal 2

Architecture (Slide 21): the voice path must answer in under a second, so the
tool only APPENDS ONE LINE to tickets/inbox.jsonl and returns. The slow work
(drafting + sending an email) happens in worker.py, a separate process that
watches that file. A text file as a job queue — production swaps in
Redis/SQS, same shape.
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dispatcher")

app = FastAPI(title="M2 Dispatcher")

TICKETS_FILE = Path("tickets/inbox.jsonl")   # the flag file worker.py watches
MAX_TOOL_ROUNDS = 4                          # the loop cap (Slide 18: it's a loop, not an if)


# --------------------------------------------------------------------------
# Provided: config helpers + xAI client (unchanged from week 1).
# Grok chat = OpenAI SDK; STT/TTS = native xAI REST endpoints via `requests`.
# --------------------------------------------------------------------------

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
    tools_used: list[str] = field(default_factory=list)  # shown as chips in the page


# --------------------------------------------------------------------------
# Provided: conversation memory (Slide 19 — tools force memory).
#
# Week 1 was stateless. The tool loop is a conversation WITHIN one turn, and
# follow-ups ("did you file it?") need history ACROSS turns — so the message
# list now lives at module level and grows. In-RAM is fine for the course
# (one user per server); production keeps per-call state in a store.
# --------------------------------------------------------------------------

HISTORY: list[dict] = []

SYSTEM_PROMPT = (
    "You are the after-hours phone dispatcher for Kindred Property Management. "
    "You are speaking aloud with a tenant, so reply in one to three short "
    "conversational sentences — no markdown, no lists, never read raw JSON. "
    "When a tenant reports something broken, use your file_maintenance_ticket "
    "tool. Collect the unit number and a short problem description first; ask "
    "for anything missing rather than guessing. After filing, confirm the "
    "ticket id naturally in words."
)


# --------------------------------------------------------------------------
# YOUR HOMEWORK 1 — the tool schemas (Slide 17).
#
# TOOLS is the list you pass as `tools=` on chat.completions.create. Each
# entry describes ONE Python function to the model. Remember:
#   * DESCRIPTIONS ARE PROMPTS — Grok decides when to call your tool by
#     reading them. "Use when a tenant reports something broken" beats
#     "files a ticket".
#   * Constrain what you can: urgency is an enum, not free text.
#   * `required` fields make the model ASK the caller for missing info
#     instead of inventing it — exactly what you want on a phone call.
#
# The first schema is written for you. Write the second one yourself for
# check_ticket_status(ticket_id) — one required string argument.
# --------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "file_maintenance_ticket",
            "description": (
                "File a maintenance work order. Use whenever a tenant reports "
                "something broken, leaking, or not working in their unit. "
                "Collect the unit number and a short problem description from "
                "the tenant before calling this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unit": {
                        "type": "string",
                        "description": "The tenant's unit number, e.g. '4B'.",
                    },
                    "problem": {
                        "type": "string",
                        "description": "Short description of what is broken.",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["emergency", "urgent", "routine"],
                        "description": (
                            "emergency = danger or major damage now (gas, flood); "
                            "urgent = no heat, no water, security issue; "
                            "routine = everything else."
                        ),
                    },
                },
                "required": ["unit", "problem", "urgency"],
            },
        },
    },
    # TODO (HOMEWORK 1): add the schema for check_ticket_status(ticket_id) here.
]


# --------------------------------------------------------------------------
# YOUR HOMEWORK 2 — the tool implementations (Slides 19 & 21).
#
# Rules of the voice path:
#   * Return in well under 100 ms — append a line, read a file. NO slow work,
#     NO network calls, NO email. The worker does that.
#   * Return a TERSE JSON STRING the model can speak from.
#   * VALIDATE arguments — the model will happily invent a unit number.
#   * Errors are returned as strings too (run_tool below does this for you):
#     the model reads {"error": ...} and asks the caller to clarify.
# --------------------------------------------------------------------------

def file_maintenance_ticket(unit: str, problem: str, urgency: str) -> str:
    """Append one JSON line to TICKETS_FILE and return {"ticket_id", "status"}.

    TODO (HOMEWORK 2): implement.
      1. Build the ticket dict: id (use new_ticket_id()), unit, problem,
         urgency, and time.time() as "filed_at".
      2. TICKETS_FILE.parent.mkdir(exist_ok=True), then append
         json.dumps(ticket) + "\\n" to the file (open in "a" mode).
      3. Return json.dumps({"ticket_id": ..., "status": "filed"}).
    """
    raise NotImplementedError("HOMEWORK 2: file_maintenance_ticket")


def check_ticket_status(ticket_id: str) -> str:
    """Look the ticket up in TICKETS_FILE (and the worker's outbox) and return
    a terse JSON status.

    TODO (HOMEWORK 2): implement.
      1. Read TICKETS_FILE line by line (it may not exist yet), json.loads
         each line, find the matching id.
      2. Not found -> return json.dumps({"error": f"no ticket {ticket_id}"}).
      3. Found -> status is "filed"; bonus: if outbox/<ticket_id>.eml exists,
         the worker already dispatched it -> status "dispatched to maintenance".
      4. Return json.dumps({"ticket_id": ..., "status": ..., "problem": ...}).
    """
    raise NotImplementedError("HOMEWORK 2: check_ticket_status")


def new_ticket_id() -> str:
    """T-1000, T-1001, ... — numbered by how many tickets are already filed."""
    count = 0
    if TICKETS_FILE.exists():
        count = sum(1 for line in TICKETS_FILE.read_text().splitlines() if line.strip())
    return f"T-{1000 + count}"


# Provided: the dispatcher between the model's request and your functions.
# Note it never raises — failures go back to the model AS TEXT, which turns
# an exception into a conversational repair ("hmm, I don't see that unit...").
def run_tool(name: str, args: dict) -> str:
    log.info("tool call: %s(%s)", name, json.dumps(args))
    try:
        if name == "file_maintenance_ticket":
            return file_maintenance_ticket(**args)
        if name == "check_ticket_status":
            return check_ticket_status(**args)
        return json.dumps({"error": f"unknown tool: {name}"})
    except Exception as exc:
        log.exception("tool %s failed", name)
        return json.dumps({"error": str(exc)})


# --------------------------------------------------------------------------
# YOUR HOMEWORK 3 — the tool-call loop (Slide 18).
#
# As shipped, think() makes ONE plain Grok call with no tools — the scaffold
# talks on day one (that's step 0; run it before writing any tool code).
# Replace the "step 0" block with the loop sketched in comments below it.
# --------------------------------------------------------------------------

async def think(transcript: str, timer: StageTimer) -> tuple[str, list[str]]:
    """Run the brain: history + transcript in, (spoken reply, tools used) out."""
    HISTORY.append({"role": "user", "content": transcript})
    client = xai_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *HISTORY]

    # ---- Step 0 (works today): one plain call, no tools ---------------------
    # Delete this block once your loop below works.
    chat = client.chat.completions.create(
        model=os.environ.get("CHAT_MODEL", "grok-4"),
        messages=messages,
    )
    reply_text = chat.choices[0].message.content or "Sorry, I lost my train of thought."
    HISTORY.append({"role": "assistant", "content": reply_text})
    return reply_text, []

    # ---- The tool-call loop (HOMEWORK 3) ------------------------------------
    # tools_used: list[str] = []
    # for _round in range(MAX_TOOL_ROUNDS):
    #     msg = client.chat.completions.create(
    #         model=os.environ.get("CHAT_MODEL", "grok-4"),
    #         messages=[{"role": "system", "content": SYSTEM_PROMPT}, *HISTORY],
    #         tools=TOOLS,
    #     ).choices[0].message
    #
    #     if not msg.tool_calls:                      # round done: model spoke
    #         reply_text = msg.content or "Sorry, I lost my train of thought."
    #         HISTORY.append({"role": "assistant", "content": reply_text})
    #         return reply_text, tools_used
    #
    #     # The model wants tools. FIRST append its tool-call message —
    #     # forgetting this is the classic 400 error (Slide 18) —
    #     HISTORY.append({
    #         "role": "assistant",
    #         "content": msg.content,
    #         "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
    #     })
    #     # — THEN run each tool and append its result, matched by id.
    #     for tc in msg.tool_calls:
    #         args = json.loads(tc.function.arguments)   # arguments arrive as a STRING
    #         result = run_tool(tc.function.name, args)
    #         tools_used.append(tc.function.name)
    #         HISTORY.append({
    #             "role": "tool",
    #             "tool_call_id": tc.id,
    #             "content": result,
    #         })
    #     # ...and loop: the model reads the results and either speaks or
    #     # calls another tool (e.g. files a ticket, then checks it).
    #
    # return "Sorry, I got stuck using my tools. Please try again.", tools_used


# --------------------------------------------------------------------------
# Provided: the week-1 cascade, upgraded to call think().
# STT and TTS are native xAI endpoints (NOT the OpenAI SDK) — see week 1.
# --------------------------------------------------------------------------

async def answer(audio: bytes, mime: str, timer: StageTimer) -> AgentReply:
    api_key = require_env("XAI_API_KEY")

    with timer.stage("stt"):
        resp = requests.post(
            "https://api.x.ai/v1/stt",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (f"clip.{ext_for(mime)}", audio, mime)},
        )
        resp.raise_for_status()
        transcript = resp.json()["text"]
    log.info("heard: %r", transcript)

    # The brain stage now contains the WHOLE tool loop — one llm number on the
    # latency bar. Watch it roughly double when a tool fires (Slide 20).
    with timer.stage("llm"):
        reply_text, tools_used = await think(transcript, timer)
    log.info("reply: %r (tools: %s)", reply_text, tools_used or "none")

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
        tools_used=tools_used,
    )


def ext_for(mime: str) -> str:
    return mime.split(";")[0].split("/")[-1] or "webm"


# --------------------------------------------------------------------------
# Provided: HTTP plumbing (week 1 + X-Tools header + /reset).
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
        except Exception as exc:
            log.exception("answer() failed")
            return Response(content=str(exc), status_code=500, media_type="text/plain")

    headers = {
        "X-Timings": json.dumps(timer.timings_ms),
        "X-Tools": json.dumps(reply.tools_used),
    }
    if reply.transcript is not None:
        headers["X-Transcript"] = json.dumps(reply.transcript)
    if reply.reply_text is not None:
        headers["X-Reply"] = json.dumps(reply.reply_text)

    return Response(content=reply.audio, media_type=reply.mime, headers=headers)


@app.post("/reset")
async def reset() -> dict:
    """Clear the conversation (the page's 'new call' button)."""
    HISTORY.clear()
    log.info("conversation reset")
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
