"""M2 "Dispatcher" — INSTRUCTOR REFERENCE SOLUTION. Do not distribute before
the milestone deadline.

Identical to the student scaffold except homeworks 1-3 are implemented (and
the static mount falls back to ../static so it runs from this directory):

    uvicorn server:app --reload --port 8000
    python ../worker.py        # or solution/worker.py for the LLM drafter

Grading: graded on behavior. Report a broken heater with a unit number ->
spoken confirmation with a ticket id + a line in tickets/inbox.jsonl; ask for
the status -> correct spoken answer; the worker turns the ticket into an
email in outbox/. Then ask one random "explain this function" question.
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

app = FastAPI(title="M2 Dispatcher (solution)")

TICKETS_FILE = Path("tickets/inbox.jsonl")
OUTBOX = Path("outbox")
MAX_TOOL_ROUNDS = 4


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
    tools_used: list[str] = field(default_factory=list)


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
# HOMEWORK 1 — the tool schemas.
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
    {
        "type": "function",
        "function": {
            "name": "check_ticket_status",
            "description": (
                "Look up the current status of a previously filed maintenance "
                "ticket. Use when the tenant asks what happened to their "
                "ticket or whether help is on the way."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ticket id, e.g. 'T-1002'.",
                    },
                },
                "required": ["ticket_id"],
            },
        },
    },
]


# --------------------------------------------------------------------------
# HOMEWORK 2 — the tool implementations. Fast, terse, validated.
# --------------------------------------------------------------------------

def file_maintenance_ticket(unit: str, problem: str, urgency: str) -> str:
    # Validate — the model WILL invent arguments if the prompt lets it.
    if urgency not in ("emergency", "urgent", "routine"):
        return json.dumps({"error": f"invalid urgency: {urgency}"})
    if not unit.strip() or not problem.strip():
        return json.dumps({"error": "unit and problem are required"})

    ticket = {
        "id": new_ticket_id(),
        "unit": unit.strip(),
        "problem": problem.strip(),
        "urgency": urgency,
        "filed_at": time.time(),
    }
    TICKETS_FILE.parent.mkdir(exist_ok=True)
    with TICKETS_FILE.open("a") as f:            # append = the whole "write" path
        f.write(json.dumps(ticket) + "\n")
    log.info("ticket filed: %s", ticket)
    return json.dumps({"ticket_id": ticket["id"], "status": "filed"})


def check_ticket_status(ticket_id: str) -> str:
    if not TICKETS_FILE.exists():
        return json.dumps({"error": f"no ticket {ticket_id}"})
    for line in TICKETS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        ticket = json.loads(line)
        if ticket["id"] == ticket_id:
            # If the worker already produced the email, the order is dispatched.
            dispatched = (OUTBOX / f"{ticket_id}.eml").exists()
            return json.dumps({
                "ticket_id": ticket_id,
                "status": "dispatched to maintenance" if dispatched else "filed, awaiting dispatch",
                "problem": ticket["problem"],
                "urgency": ticket["urgency"],
            })
    return json.dumps({"error": f"no ticket {ticket_id}"})


def new_ticket_id() -> str:
    count = 0
    if TICKETS_FILE.exists():
        count = sum(1 for line in TICKETS_FILE.read_text().splitlines() if line.strip())
    return f"T-{1000 + count}"


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
# HOMEWORK 3 — the tool-call loop.
# --------------------------------------------------------------------------

async def think(transcript: str, timer: StageTimer) -> tuple[str, list[str]]:
    HISTORY.append({"role": "user", "content": transcript})
    client = xai_client()
    tools_used: list[str] = []

    for _round in range(MAX_TOOL_ROUNDS):
        msg = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "grok-4"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *HISTORY],
            tools=TOOLS,
        ).choices[0].message

        if not msg.tool_calls:
            reply_text = msg.content or "Sorry, I lost my train of thought."
            HISTORY.append({"role": "assistant", "content": reply_text})
            return reply_text, tools_used

        # FIRST the assistant's tool-call message (the classic missed step)...
        HISTORY.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })
        # ...THEN each result, matched by tool_call_id.
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)   # a STRING until you parse it
            result = run_tool(tc.function.name, args)
            tools_used.append(tc.function.name)
            HISTORY.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "Sorry, I got stuck using my tools. Please try again.", tools_used


# --------------------------------------------------------------------------
# Provided: the cascade (native xAI STT/TTS, Grok chat via the SDK).
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
    HISTORY.clear()
    log.info("conversation reset")
    return {"ok": True}


static_dir = "static" if os.path.isdir("static") else "../static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
