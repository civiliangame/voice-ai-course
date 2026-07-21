"""M2 "Dispatcher" — the background worker (Lecture 2, Slides 21-22).

This is the OTHER HALF of the flag-file pattern, and a separate process on
purpose. Run it in a second terminal next to the server:

    python worker.py            # watches tickets/inbox.jsonl forever
    python worker.py --once     # drain the backlog and exit (handy for grading)

What it does, every 2 seconds:

    1. Read tickets/inbox.jsonl — the flag file the voice agent's tool appends to.
    2. Skip tickets whose id is already in tickets/processed.txt (the ledger:
       this is what makes redelivery safe — at-least-once + idempotency,
       implemented with a text file).
    3. For each NEW ticket: draft an email, "send" it (written to outbox/ as
       a .eml file so the whole class can read the result), record the id.

Why a separate process (Slide 21)? The phone call must answer in under a
second, so the tool only writes the flag and returns. If this worker crashes,
the call is unaffected and the ticket is still in the file. If the call
drops, the ticket already survived. The file is the contract between the two.

YOUR HOMEWORK 4 (search: HOMEWORK 4): as shipped, draft_email() returns a
boring fixed template — the worker runs out of the box, even with no API key.
Upgrade it to a Grok call: this worker gets its OWN LLM with its OWN prompt
(Slide 22 — "two brains"). The voice model is optimized to converse; this one
is optimized to produce an artifact. Nobody is waiting on it, so it has no
latency pressure — and it could even be a smaller, cheaper model.
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

TICKETS_FILE = Path("tickets/inbox.jsonl")     # written by the server's tool
PROCESSED_FILE = Path("tickets/processed.txt") # our ledger of handled ids
OUTBOX = Path("outbox")                        # "sent" emails land here
POLL_SECONDS = 2

MAINTENANCE_EMAIL = os.environ.get("MAINTENANCE_EMAIL", "oncall@kindredpm.example")

# The worker's OWN system prompt — compare it with the server's. Same API,
# same model family, opposite instructions: this one may be long and formal
# because its output is an email, not speech.
DRAFTER_PROMPT = (
    "You draft work-order emails to a maintenance contractor for Kindred "
    "Property Management. Given a ticket as JSON, write a clear, professional "
    "email body: what is broken, where (unit), how urgent, and what action is "
    "requested. Plain text only, ready to send, no subject line, no "
    "placeholders. Sign as 'KPM Dispatch (automated)'."
)


def draft_email(ticket: dict) -> str:
    """Ticket dict in, email body out.

    As shipped: a fixed template, so the pipeline works end-to-end before you
    write any LLM code (same echo-first idea as week 1).

    TODO (HOMEWORK 4): replace the template with a one-shot Grok call —
    LLM-as-function: JSON in, email out. No conversation, no history.

        client = OpenAI(
            base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
            api_key=os.environ["XAI_API_KEY"],
        )
        chat = client.chat.completions.create(
            model=os.environ.get("WORKER_MODEL", os.environ.get("CHAT_MODEL", "grok-4")),
            messages=[
                {"role": "system", "content": DRAFTER_PROMPT},
                {"role": "user", "content": json.dumps(ticket)},
            ],
        )
        return chat.choices[0].message.content

    Think about failure: if the API call raises, the ticket id is never
    recorded as processed, so the next poll retries it. Free retry semantics —
    because the ledger only advances on success.
    """
    return (
        f"Automated work order {ticket['id']}\n\n"
        f"Unit:     {ticket['unit']}\n"
        f"Problem:  {ticket['problem']}\n"
        f"Urgency:  {ticket['urgency']}\n\n"
        f"Please schedule service.\n\n-- KPM Dispatch (automated)"
    )


# --------------------------------------------------------------------------
# Provided: delivery + the ledger. send_email() writes a .eml file so the
# class can read every "sent" email. Real SMTP is the stretch goal — swap the
# body of send_email() for smtplib and nothing else changes (that interface
# stability is the point of keeping delivery in one function).
# --------------------------------------------------------------------------

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
    """Everything in the inbox that isn't in the ledger yet."""
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
            body = draft_email(ticket)      # the (eventually) LLM step
            send_email(ticket, body)
            mark_processed(ticket["id"])    # ledger advances ONLY on success
            handled += 1
        except Exception:
            log.exception("failed on %s — will retry next poll", ticket["id"])
    return handled


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatcher ticket worker")
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
