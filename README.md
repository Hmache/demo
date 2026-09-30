# demo

Turn **a URL + a scenario written in plain text** into a narrated product demo video.

Headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in — plus a production layer: title / section / outro cards with crossfades, a framed browser on a brand-tinted gradient, chapter labels, a presenter bubble (your photo + live voice bars), logo watermark, spotlight highlights, zooms, callouts, keyboard badges, a progress bar, a QR code on the outro, a phone preset and ducked background music (generated if you have none). Output: MP4 (+ optional GIF and `.srt` captions), and a `review.png` contact sheet to check the result at a glance.

Built as an agent skill (`SKILL.md`), but the scripts work on their own too.

## Write a scenario

`scenario.txt` — settings at the top, then one block per step. Normal lines are the narration, lines starting with `>` are actions. Targets are the text you see on screen.

```text
url: https://app.example.com
template: launch
title: Acme Orders
outro: Try it free at acme.com
qr: https://acme.com/signup
music: auto

## The dashboard

# Everything in one place
Here's the dashboard: every order from the last 30 days in one place.

# Find a customer
Let's find a customer by name.
> type "Dupont" into "Search"
> press Enter

One click opens the full order history.
> click "Dupont SARL"
> zoom into "Total" x2
> callout "Loads in under a second" at "Order history"
```

Actions: `click` · `hover over` · `type "…" into` · `fill … with "…"` · `select "…" in` · `press` · `scroll down / up / to` · `highlight` · `zoom into` / `zoom out` · `callout "…" at` · `dismiss cookies` · `wait 2s` · `wait for` · `go to` · `js:`.

Structure: `## Title` = section card, `# Title` = chapter label. Settings: `template` (launch / walkthrough / social / mobile / minimal), `size`, `hd`, `frame`, `transitions`, `presenter` + `photo`, `logo`, `qr`, `title`, `subtitle`, `outro`, `brand color`, `progress bar`, `highlight clicks`, `show keys`, `cookies: dismiss`, `captions`, `music`, `gif`, `voice`, `engine`, `lang`, `speed`, `typing speed`, `login state`. Use `#2` for the 2nd match, or a CSS selector when the text is ambiguous. `$VAR` in typed text is read from the environment at render time (for logins). See [`example-scenario.txt`](example-scenario.txt) and the full reference in [`SKILL.md`](SKILL.md).

## Run it

```bash
bash setup.sh                                   # Playwright, Kokoro TTS model, Inter font (idempotent)
node record.js scenario.txt out --explore=0     # list what's clickable on the page + screenshot
bash make.sh scenario.txt out demo.mp4          # narration -> dry run -> recording -> mix -> review.png
```

Requirements: Node 18+, Python 3.10+, ffmpeg.

## How it works

1. **Narration first** — `tts.py` generates one voice clip per step and measures its length.
2. **Record to the voice's timing** — `record.js` plays the steps with Playwright and holds each step at least as long as its narration. Frames come from the Chrome DevTools screencast, timestamped on the same clock as the steps, so audio and video stay in sync (within ~50 ms).
3. **Mix** — `mix.py` places each clip at its step's start, burns in captions (Inter), optionally ducks music, and encodes H.264 MP4.

`scenario.py` turns the text file into the JSON the scripts use internally; `check.py` builds the review sheet and checks voice sync.

## Voices

| Engine | Notes |
|---|---|
| `kokoro` (default) | Free, runs locally, no API key. 50+ voices in 9 languages, blendable (`af_heart*0.7+af_sky*0.3`). |
| `openai` | `OPENAI_API_KEY`, natural in French/English, tone via `instructions`. |
| `elevenlabs` | `ELEVENLABS_API_KEY`, best quality, voice cloning. |
| `none` | Silent video, captions only. |

Every clip is prepared for speech (URLs, prices, units, symbols, `pronounce: Parla=Par-la`) and polished (silence trim, EQ, compression, −16 LUFS loudness). `python3 tts.py --preview "a line" out fr-fr` renders the line in every voice for a language so you can pick one.

## License

MIT
