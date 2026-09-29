# demo

Turn **a URL + a scenario written in plain text** into a narrated product demo video.

Headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in — plus optional title/outro cards, spotlight highlights, zooms, a progress bar, a phone preset and ducked background music. Output: MP4 (+ optional GIF and `.srt` captions), and a `review.png` contact sheet to check the result at a glance.

Built as an agent skill (`SKILL.md`), but the scripts work on their own too.

## Write a scenario

`scenario.txt` — settings at the top, then one block per step. Normal lines are the narration, lines starting with `>` are actions. Targets are the text you see on screen.

```text
url: https://app.example.com
voice: af_heart
title: Acme Orders
outro: Try it free at acme.com
cookies: dismiss

Here's the dashboard: every order from the last 30 days in one place.

Let's find a customer by name.
> type "Dupont" into "Search"
> press Enter

One click opens the full order history.
> click "Dupont SARL"
> zoom into "Total" x2
```

Actions: `click` · `hover over` · `type "…" into` · `fill … with "…"` · `select "…" in` · `press` · `scroll down / up / to` · `highlight` · `zoom into` / `zoom out` · `dismiss cookies` · `wait 2s` · `wait for` · `go to` · `js:`.

Settings: `size` (or `mobile`, `square`, `vertical`…), `hd`, `title`, `subtitle`, `outro`, `brand color`, `progress bar`, `highlight clicks`, `cookies: dismiss`, `captions`, `music`, `gif`, `voice`, `engine`, `lang`, `speed`, `typing speed`, `login state`. Use `#2` for the 2nd match, or a CSS selector when the text is ambiguous. See [`example-scenario.txt`](example-scenario.txt) and the full reference in [`SKILL.md`](SKILL.md).

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
| `kokoro` (default) | Free, runs locally, no API key. Great in English; one French voice (`ff_siwis`). |
| `openai` | `OPENAI_API_KEY`, natural in French/English, tone via `instructions`. |
| `elevenlabs` | `ELEVENLABS_API_KEY`, best quality, voice cloning. |
| `none` | Silent video, captions only. |

## License

MIT
