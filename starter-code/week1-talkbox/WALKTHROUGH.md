# Week 1 Code Walkthrough — teaching the Talkbox scaffold alongside the slides

Instructor-facing. This maps every piece of the scaffold to the lecture slide
where you teach it, with what to show on screen and what to say. Total live
coding/demo time: ~25 minutes across three segments (slides 10, 13, 14).

---

## Segment A · Slide 10 ("the browser path") — `static/index.html`, top comment + §1

**Show:** the comment block at the top of `index.html`, then the `init()`
function (§1).

**Teach:**

- The whole browser path from the slide is four lines of the diagram and ~100
  lines of JS: `getUserMedia` → `MediaRecorder` → `fetch POST` → `Audio.play()`.
- Point at `getUserMedia({audio: true})`: this is the permission prompt, and it
  is the reason for the "must be localhost or HTTPS" pitfall — the API simply
  doesn't exist on insecure origins. Students who deploy to `http://myvm:8000`
  will hit this Sunday night; say it now.
- Point at the `mimeType` selection: the browser hands us **compressed** audio
  (webm/Opus; Safari gives mp4). Ask the class: "is that OK to send to STT?"
  Answer: only if the docs say so — foreshadows the week's #2 failure mode.
  Raw PCM samples arrive in week 2; this week compressed clips are fine
  *because the STT endpoint accepts container formats*.
- Draw the correspondence from the slide one more time, now with code on
  screen: browser mic ≈ caller, HTTP POST ≈ provider media stream (we upgrade
  the POST to a WebSocket in week 2, and nothing else changes shape).

**Don't** walk through the rendering code (§4) — mention the latency bar
exists and move on; it pays off in Segment C.

---## Segment B · Slide 13 ("the xAI API in 90 seconds") — `hello_grok.py`

**Show:** `hello_grok.py`, whole file. Everyone runs it live, in class.

**Teach:**

- One base URL, one key, one SDK you already know: `OpenAI(base_url=
  "https://api.x.ai/v1", api_key=...)`. There is no "xAI SDK" to learn —
  that's the whole slide. But this applies to **Grok chat only**.
- **Correction to teach explicitly:** xAI's STT and TTS are NOT OpenAI-SDK
  compatible. `client.audio.transcriptions`/`client.audio.speech` POST to
  `/v1/audio/*`, which xAI does not serve — a 404. STT/TTS are native REST
  endpoints (`POST /v1/stt`, `POST /v1/tts`) called directly with `requests`;
  only `client.chat.completions` (Grok) uses the SDK. Full reference in
  `solution/`.
- Config: open **docs.x.ai live** on the projector. Students need `CHAT_MODEL`
  (a Grok model name) and `TTS_VOICE` (an xAI voice_id like `eve`) in `.env` —
  STT needs neither. Do not read these off the slide — handouts rot, docs don't.
- Wait until everyone gets a printed sentence. A key or billing failure found
  now costs 2 minutes; found Sunday it costs the milestone. This is the
  highest-value 5 minutes of the lecture.

---

## Segment C · Slide 14 ("Milestone 1: Talkbox") — `server.py` tour

**Show:** `server.py`, in this order (it's designed to be read top-down on a
projector):

### 1. The module docstring
"You edit exactly one function." Set expectations: the scaffold is not
mysterious, it's ~180 lines and they should read all of it — the AI-assistant
policy (explain any line on demand) applies to scaffold code they submit too.

### 2. `answer_endpoint()` — the provided plumbing (bottom of file)
- `await request.body()` → the clip; content-type header → the format.
  This is the server end of Segment A's `fetch`.
- The `try/except` returns errors as text to the browser: "when your cascade
  breaks — it will — the error appears on the page, not just in a terminal
  you forgot to look at."
- Timings and transcripts ride back as **headers** next to the audio body.
  Tie to slide 6: "transcripts for free" is the cascade's superpower, and
  we're using it from day one to debug.

### 3. `StageTimer` — instrumentation as a first-class requirement
- Show the `stage()` context manager (10 lines). Wrapping a stage costs one
  `with` line; there is no excuse for unmeasured stages.
- Say the pedagogical quiet part out loud: "your homework produces the latency
  budget from slide 5, measured by you, on your wifi, with your key. Week 4's
  streaming work will be justified by *your* numbers, not mine."

### 4. `answer()` — the homework
- Run the scaffold as-is, hold the button, let the class hear the echo.
  **The echo is step 0 of the homework**: it proves mic → server → speaker
  with zero API calls, so every later bug is in their cascade, not plumbing.
- Walk the commented skeleton of the three calls. Three things to stress:
  1. **Sequential + blocking is correct this week.** Point at the three
     `with timer.stage(...)` blocks: weeks 2–4 exist to overlap these; week 5
     makes blocking the event loop a firing offense. Resist optimizing.
  2. **The system prompt is speech-aware**: it tells Grok its words will be
     read aloud (short sentences, no markdown). First taste of week 4's
     "prompting for speech."
  3. **`require_env` fails with a docs pointer**, and echo mode needs no
     config at all — students can't get stuck on setup before hearing sound.

### 5. (Optional, 2 min) Run the reference solution
From `solution/`, demo a full turn. Then click through the latency bar on the
page: STT ~x ms, Grok ~y ms, TTS ~z ms, and a gray "network/other" segment.
Ask: "where did the gray milliseconds go?" (Answer: upload, download, playback
start — the parts of slide 5's budget that no API dashboard shows you.)

---

## Segment D · Slide 15 (homework) — what to collect

1. Working Talkbox (TA talks to it; ask one random "explain this function").
2. Their three stage timings + one sentence on the surprise. Most students
   expect Grok to dominate; often TTS or STT does — that surprise is the hook
   for week 4.
3. The conceptual question ("what must become automatic before it's a phone
   call?") — **keep these answers**; they are the course syllabus rediscovered,
   and you re-show them in week 6.

## Anticipated student questions

- *"Why HTTP POST and not WebSocket?"* — Because week 1 has exactly one
  request per turn, and push-to-talk gives us turn boundaries for free.
  The moment we remove the button (week 3) turns stop being requests.
- *"Can I use `async`/`await` on the API calls?"* — Sure, but it buys nothing
  while calls are sequential. Concurrency arrives when there's something to
  overlap (week 2).
- *"MediaRecorder gives me chunks — why collect then send, not stream?"* —
  You've just invented week 2's milestone. Hold that thought.
- *"Why does my first request take an extra second?"* — TLS + connection
  setup to the API; watch the gray bar shrink on turn two. (Connection reuse
  is why the solution builds one client per request but the SDK pools under
  the hood; week 5 revisits session lifetime properly.)
