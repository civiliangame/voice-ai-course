"""M2 "Dispatcher" worker — INSTRUCTOR REFERENCE SOLUTION (homework 4).

Same as the scaffold worker but draft_email() is a one-shot Grok call, with
the template kept as a fallback: if the API errors, the ticket stays
unprocessed (ledger only advances on success) and is retried next poll.

Run from the milestone directory so the paths line up:

    python solution/worker.py [--once]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

TICKETS_FILE = Path("tickets/inbox.jsonl")
PROCESSED_FILE = Path("tickets/processed.txt")
OUTBOX = Path("outbox")
POLL_SECONDS = 2

MAINTENANCE_EMAIL = os.environ.get("MAINTENANCE_EMAIL", "oncall@kindredpm.example")

DRAFTER_PROMPT = (
    "You draft work-order emails to a maintenance contractor for Kindred "
    "Property Management. Given a ticket as JSON, write a clear, professional "
    "email body: what is broken, where (unit), how urgent, and what action is "
    "requested. Plain text only, ready to send, no subject line, no "
    "placeholders. Sign as 'KPM Dispatch (automated)'."
)


def draft_email(ticket: dict) -> str:
    """HOMEWORK 4: LLM-as-function — ticket JSON in, email body out.

    The worker gets its own model and its own prompt (Slide 22, "two brains"):
    the voice path converses; this one produces an artifact, with zero latency
    pressure — which is why WORKER_MODEL may be a smaller, cheaper model.
    """
    client = OpenAI(
        base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
        api_key=os.environ["XAI_API_KEY"],
    )
    chat = client.chat.completions.create(
        model=os.environ.get("WORKER_MODEL") or os.environ.get("CHAT_MODEL", "grok-4"),
        messages=[
            {"role": "system", "content": DRAFTER_PROMPT},
            {"role": "user", "content": json.dumps(ticket)},
        ],
    )
    body = chat.choices[0].message.content
    if not body:
        raise RuntimeError("empty draft from model")
    return body


def send_email(ticket: dict, body: str) -> Path:
    OUTBOX.mkdir(exist_ok=True)
    urgent = ticket["urgency"] in ("emergency", "urgent")
    subject = f"{'[URGENT] ' if urgent else ''}Work order {ticket['id']} — unit {ticket['unit']}"
    path = OUTBOX / f"{ticket['id']}.eml"
    path.write_text(
        f"To: {MAINTENANCE_EMAIL}\n"
        f"From: dispatch@kindredpm.example\n"
        f"Subject: {subject}\n\n"
        f"{body}\n"
    )
    log.info("EMAIL SENT -> %s (%s)", path, subject)
    return path


def load_processed() -> set[str]:
    if PROCESSED_FILE.exists():
        return set(PROCESSED_FILE.read_text().split())
    return set()


def mark_processed(ticket_id: str) -> None:
    PROCESSED_FILE.parent.mkdir(exist_ok=True)
    with PROCESSED_FILE.open("a") as f:
        f.write(ticket_id + "\n")


def pending_tickets() -> list[dict]:
    if not TICKETS_FILE.exists():
        return []
    processed = load_processed()
    tickets = []
    for line in TICKETS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        ticket = json.loads(line)
        if ticket["id"] not in processed:
            tickets.append(ticket)
    return tickets


def process_once() -> int:
    handled = 0
    for ticket in pending_tickets():
        log.info("new ticket: %s (unit %s, %s)", ticket["id"], ticket["unit"], ticket["urgency"])
        try:
            body = draft_email(ticket)
            send_email(ticket, body)
            mark_processed(ticket["id"])   # ledger advances ONLY on success
            handled += 1
        except Exception:
            log.exception("failed on %s — will retry next poll", ticket["id"])
    return handled


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatcher ticket worker (solution)")
    parser.add_argument("--once", action="store_true", help="drain the backlog and exit")
    args = parser.parse_args()

    if args.once:
        n = process_once()
        log.info("done: %d ticket(s) processed", n)
        return

    log.info("watching %s (Ctrl-C to stop)", TICKETS_FILE)
    while True:
        process_once()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
