# Week 2 — Audio for Engineers Who Skipped DSP

**Duration**: 75–90 min · **Milestone**: M2 "Plumber"

## Objectives

Students can manipulate raw audio in Python with confidence: PCM, sample rates, µ-law companding, framing, resampling, and buffered playback. This is the least glamorous and most load-bearing week — every later bug that "sounds weird" traces back to this material.

## Slide-by-Slide

### Slide 1 — Title: "Audio for Engineers Who Skipped DSP"
- "Today: sound becomes numbers, numbers become bugs"

**Speaker notes**: Promise them: after today, `int16`, `8000 Hz`, and `µ-law` will never scare them again. Everything is just arrays.

### Slide 2 — Sound → Numbers: Sampling & Quantization
- Sampling rate: measurements per second (8 kHz phone, 16 kHz speech models, 24 kHz TTS output, 44.1 kHz music)
- Nyquist in one line: you can represent frequencies up to half your sample rate
- Bit depth: int16 PCM is the lingua franca (−32768…32767)
- One second of phone audio = 8,000 × 2 bytes = 16 KB

**Speaker notes**: Show a 50 ms waveform zoomed until individual samples are visible dots. Demystify: "an audio buffer is a numpy int16 array; that's it."

### Slide 3 — Why Phones Sound Like Phones: 8 kHz and G.711
- The phone network standardized on 8 kHz / 64 kbps in the 1970s — and it's still the floor today
- 8 kHz captures up to ~4 kHz of frequency: enough for intelligible speech, bad for "s" vs "f"
- Speech AI models want 16 kHz+ → we must upsample everything coming off a phone line
- Consequence: your model literally hears worse on the phone path than the browser path

**Speaker notes**: Play the same sentence at 44.1 kHz then downsampled to 8 kHz. The class will *hear* the week's motivation.

### Slide 4 — µ-law: Logarithmic Compression from 1972 That You Still Must Handle
- G.711 µ-law (US/Japan) / A-law (Europe): 16-bit linear → 8-bit logarithmic
- Why log? Human hearing is logarithmic — spend precision on quiet sounds
- Halves the bandwidth; still the default encoding telephony providers stream to you
- In Python: a 256-entry lookup table, or `audioop`/library one-liners; decode µ-law → int16 PCM before doing anything else

**Speaker notes**: Show the companding curve. Key operational point: the *first* thing a production pipeline does to inbound phone audio is base64-decode, then µ-law-decode to linear PCM. Get the order wrong and you get loud static — a rite of passage.

### Slide 5 — Frames: Audio Arrives in 20 ms Pieces
- Telephony streams deliver ~20 ms chunks (160 samples at 8 kHz) at a steady cadence — 50 msgs/sec
- Why fixed small frames: low latency, steady pacing, VAD algorithms require exact frame sizes (10/20/30 ms)
- Your pipeline must handle partial frames: buffer bytes until you have a full frame

**Speaker notes**: Emphasize cadence over size — real-time audio is a *metronome*, not a firehose. This sets up the fixed-rate sender in week 5.

### Slide 6 — Resampling: 8 k ↔ 16 k ↔ 24 k
- The rate zoo in one call: phone in at 8 k → model wants 16 k → TTS/model outputs 24 k → phone out at 8 k
- Naive approaches (drop/duplicate samples) alias and sound metallic
- Use a real resampler (polyphase filtering — e.g., the `soxr` library); treat it as a black box with a quality knob
- Gotcha: resampling chunk-by-chunk creates boundary artifacts → keep a small sliding window/overlap or use the library's streaming mode

**Speaker notes**: The boundary-artifact gotcha is a genuine production lesson: resampling each 20 ms chunk independently introduces periodic clicks. Streaming resampler state must persist across chunks. Say this twice; half of the M2 bugs will be this.

### Slide 7 — Bytes, Endianness, and the Bugs You'll Meet
- int16 little-endian is standard; getting it wrong = loud noise
- float32 [−1, 1] vs int16 [−32768, 32767]: browsers and ML models often use float, telephony uses int — convert deliberately
- Clipping: scale carefully when converting; overflow wraps and screeches
- Debug ritual: when audio sounds wrong, **write the buffer to a .wav file and look at it** in Audacity

**Speaker notes**: The .wav-and-look debug ritual will save more student hours than anything else this week. Demo it: take a "broken screeching" buffer, open in Audacity, diagnose in 10 seconds (it's byte-misaligned).

### Slide 8 — Anatomy of a Media Stream Message
- Show a full telephony media message: `{"event": "media", "streamSid": …, "media": {"payload": "<base64 µ-law>"}}`
- Other events on the same socket: `start` (call metadata), `stop`, `mark` (playback checkpoint), `clear`
- Outbound: same shape in reverse — you base64-encode µ-law and send JSON
- Our browser project mirrors this format on purpose

**Speaker notes**: Decode one live: base64 → µ-law → int16 → plot. Fifteen lines of Python from "phone call" to waveform on screen. This is the demo that makes the whole stack feel graspable.

### Slide 9 — Jitter and the Playout Buffer
- Networks deliver audio unevenly (jitter); speakers need perfectly even samples
- Solution: a playout buffer — accumulate a little audio before starting playback
- The fundamental knob: bigger buffer = smoother audio but more latency
- Real numbers: 40–100 ms of buffer is a common sweet spot for conversational audio

**Speaker notes**: This is the first appearance of the course's central tradeoff (latency vs. robustness) in concrete form. It reappears in endpointing (week 3) and pacing (week 5).

### Slide 10 — Cleaning the Signal: AEC, NS, AGC
- Real-world input is dirty: echo of the agent's own voice, background noise, wildly varying volume
- **AEC** (acoustic echo cancellation): subtract what you played from what you hear — critical for barge-in later
- **NS** (noise suppression): classical (WebRTC) or neural (RNNoise) — neural is dramatically better on non-stationary noise
- **AGC** (automatic gain control): normalize volume
- Off-the-shelf: WebRTC Audio Processing Module bundles all three; treat as a pipeline stage, not something you write

**Speaker notes**: Play a before/after of neural noise suppression on speech over a running faucet or street noise. Note the ordering matters: AEC before NS before VAD — you want the cleaned signal feeding your speech detector.

### Slide 11 — The Full Inbound Pipeline (Putting It Together)
- Diagram, one box per stage: base64 decode → µ-law decode → int16 PCM 8 k → resample 16 k → APM (AEC/NS/AGC) → [VAD, week 3] → model
- Outbound reverse: model audio 24 k → resample 8 k → µ-law encode → base64 → JSON → provider
- Each arrow is a place to log, buffer, and get bytes wrong

**Speaker notes**: This diagram is the M2 spec. Students implement exactly these boxes (minus APM, which is a stretch goal).

### Slide 11b — The Best Pipeline Is No Pipeline
- Plot twist: some realtime models speak telephony natively — the xAI Voice Agent API accepts `audio/pcmu` (G.711 µ-law, 8 kHz) directly
- A phone-to-Grok bridge can pass base64 µ-law straight through in both directions: **zero transcoding**
- So why learn all this? (1) Browsers don't speak µ-law — our project needs the pipeline; (2) the cascade path (week 4) needs PCM at model-specific rates; (3) when audio breaks in production, the debugging is exactly this material
- Design principle: prefer negotiating a common format end-to-end over converting in the middle

**Speaker notes**: This is a real production pattern: a Telnyx↔xAI bridge where both sides speak µ-law 8 kHz means the server just relays base64 strings between two WebSockets. Students should feel the elegance — and understand it's only possible because someone knew enough about codecs to configure `audio.input.format.type = "audio/pcmu"` on both ends.

### Slide 12 — Milestone 2: "Plumber"
- Upgrade Talkbox from clip-upload to **continuous audio streaming** over a WebSocket (still push-to-talk: the button now gates the stream instead of recording a file)
- Route the mic audio through a **simulated phone line** before STT: float32 (browser) → int16 → down to 8 kHz µ-law → decode → resample back up — you should *hear* and *measure* the degradation
- Buffered playout for the TTS response: stream audio back and play it smoothly (20 ms framing, playout buffer)
- Definition of done: Talkbox still answers questions over the streaming path, audio is click/screech-free, and you report STT accuracy on the same utterance with and without the phone line
- Stretch: exact `webrtcvad`-compatible 20 ms framing (sets up week 3); try a noise-suppression library

**Speaker notes**: The STT accuracy comparison makes the codec lesson concrete: students *see* the transcript get worse through the phone line, which is exactly what production phone agents live with. Diagnosis chart still applies: screeching = endianness/scaling; rhythmic clicks = chunk-boundary resampling.

### Slide 13 — Homework & Reading
- M2 due before week 3
- Conceptual question: "Your outbound audio clicks every 20 ms. What's the most likely cause and fix?"
- Conceptual question: "Why does the playout buffer size trade latency against smoothness? What happens at 0 ms? At 500 ms?"
- Deliverable: the same sentence transcribed clean vs through your phone line — include both transcripts
- Optional: read the G.711 Wikipedia page (short, genuinely good), skim `soxr` docs

## Live Demo Plan
1. Same sentence at 44.1 kHz vs 8 kHz (motivation)
2. Live REPL: decode a real media message base64 → µ-law → numpy → matplotlib waveform
3. Broken-audio debugging: open a corrupted buffer in Audacity, diagnose byte misalignment
4. Neural noise suppression before/after

## Common Pitfalls
- Resampler state not persisted across chunks (periodic clicks)
- float32/int16 scaling mistakes (silence or screeching)
- Doing µ-law decode after resampling instead of before (static)
