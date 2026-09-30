# demo

Turn **a URL + a scenario written in plain text** into a narrated product demo video — AI voice-over, captions, cards and music, rendered locally for free.

<p align="center"><img src="https://github.com/user-attachments/assets/e2cb53da-9212-44bb-a10d-c0117bb78cdd" width="800" alt="16-second preview of a demo rendered by the skill" /></p>

**Quick start** (the first run also downloads Chromium and the voice model, ~500 MB)

```bash
git clone https://github.com/Hmache/demo.git && cd demo && bash setup.sh   # Node 18+, Python 3.10+, ffmpeg
bash make.sh examples/pypi.txt out pypi-demo.mp4                        # the README video: -> out/pypi-demo.mp4 + review.png
```

Headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in — plus a production layer: title / section / outro cards with crossfades, a framed browser on a brand-tinted gradient, chapter labels, logo watermark, spotlight highlights, zooms, callouts, keyboard badges, a progress bar, a QR code on the outro, a phone preset and ducked background music (generated if you have none). Output: MP4 (+ optional GIF and `.srt` captions), and a `review.png` contact sheet to check the result at a glance.

Built as an agent skill for Claude (`SKILL.md`), but the scripts work on their own from any terminal.

A 37-second demo of pypi.org made by the skill from a 30-line scenario — title card, chapters, zoom, recap and outro, Kokoro voice, generated music:

https://github.com/user-attachments/assets/a23bea85-cb5e-4b53-be69-a828de79c04f

```text
scenario.txt  ──►  tts.py (voice clips)  ──►  record.js (Playwright + CDP screencast)  ──►  mix.py (ffmpeg)  ──►  demo.mp4
                                                                                        └──►  check.py  ──►  review.png + sync report
```

## Install

### 1. Requirements

| | |
|---|---|
| Node | 18 or newer (`node -v`) |
| Python | 3.10 or newer (`python3 -V`) |
| ffmpeg | 4.4 or newer, with `libass` (all common builds have it) |
| Disk | ~400 MB: Chromium (~170 MB), the Kokoro voice model (~330 MB shared across projects), the Inter font |

```bash
# macOS
brew install node python ffmpeg
# Debian / Ubuntu
sudo apt install -y nodejs npm python3 python3-pip ffmpeg
# Windows: use WSL2 (Ubuntu) and follow the Debian line
```

### 2. Get the scripts

Either clone the repo:

```bash
git clone https://github.com/Hmache/demo.git
cd demo
bash setup.sh
```

or drop the eight scripts into a tools folder without cloning:

```bash
mkdir -p ~/.cache/demo-video/bin && cd ~/.cache/demo-video/bin && \
for f in setup.sh make.sh scenario.py tts.py record.js mix.py check.py draft.py; do curl -fsSL -o $f https://raw.githubusercontent.com/Hmache/demo/main/$f; done && \
chmod +x *.sh && ./setup.sh
```

`setup.sh` is idempotent. It installs Playwright + Chromium, the Kokoro TTS model and voices (into `~/.cache/demo-video/models`), the Inter font, and the Python modules `kokoro-onnx`, `soundfile`, `qrcode`, `pillow`. When Playwright's browser CDN is blocked (locked-down networks), it falls back to a portable [ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium-portablelinux) from GitHub releases and `make.sh` picks it up automatically.

### 3. Optional: studio voices

The default `kokoro` engine is free and runs locally. For OpenAI or ElevenLabs voices, export the key only for the command that renders — never write it in the scenario:

```bash
OPENAI_API_KEY=sk-... bash make.sh scenario.txt out demo.mp4        # engine: openai  in scenario.txt
ELEVENLABS_API_KEY=... bash make.sh scenario.txt out demo.mp4       # engine: elevenlabs
```

### 4. Install as a Claude skill

`SKILL.md` teaches Claude (Cowork, Claude Code, or the Agent SDK) how to gather the inputs, write the scenario, render, review its own video and deliver it. Three ways to install it:

- **Claude Code / Agent SDK** — copy it into a skills folder, the scripts are downloaded on first use:
  ```bash
  mkdir -p ~/.claude/skills/demo-video && curl -fsSL -o ~/.claude/skills/demo-video/SKILL.md https://raw.githubusercontent.com/Hmache/demo/main/SKILL.md
  ```
  (use `.claude/skills/demo-video/` inside a project to scope it to that repo.)
- **Cowork (Claude desktop app)** — open Settings → Skills, add a new skill and paste the contents of `SKILL.md`. Cowork runs the pipeline in its cloud workspace by default, or on your Mac through a connected folder when the site is on `localhost` or behind a VPN.
- **Claude.ai / API** — attach `SKILL.md` to a project as instructions, or pass it as the system prompt of an agent that has a shell.

Then just ask: *"Make a demo video of https://app.example.com: sign in, open the dashboard, filter last 7 days, show the total"*. Claude writes the scenario, renders, reads `review.png` and fixes what's wrong before handing over the MP4 and the editable `scenario.txt`.

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

Structure: `## Title` = section card, `# Title` = chapter label. Use `#2` for the 2nd match, or a CSS selector when the text is ambiguous. `$VAR` in typed text is read from the environment at render time, so a login is `> fill "Password" with "$DEMO_PASS"` + `DEMO_PASS=… bash make.sh …`. See [`examples/pypi.txt`](examples/pypi.txt) (the README video), [`example-scenario.txt`](example-scenario.txt) and the full reference in [`SKILL.md`](SKILL.md).

### Templates

| `template:` | What you get |
|---|---|
| `launch` | 1080p, framed browser on a brand gradient, chapters, crossfades, progress bar, click highlights — the default for product videos |
| `walkthrough` | 1080p raw screen, chapters, progress bar — tutorials |
| `social` | 1080×1920 vertical, framed, captions — Reels / TikTok / Shorts |
| `mobile` | 390×844 phone viewport at 2×, touch cursor, framed |
| `minimal` | just the recording and the captions |

Any setting written after `template:` overrides it. Other settings: `size`, `hd`, `frame`, `transitions`, `logo`, `qr`, `title`, `subtitle`, `outro`, `brand color`, `progress bar`, `highlight clicks`, `show keys`, `cookies: dismiss`, `captions`, `recap` (chapter list card before the outro, auto with 3+ chapters), `music`, `music volume`, `gif`, `voice`, `engine`, `lang`, `speed`, `pronounce`, `typing speed`, `pause`, `login state`. `presenter: bubble` + `photo: me.jpg` adds a small pill with your photo and live voice bars; it is opt-in because it covers a corner of the page.

## Run it

```bash
bash setup.sh                                   # once
node record.js scenario.txt out --explore=0     # list what's clickable on the page + explore.png
bash make.sh scenario.txt out demo.mp4          # narration -> dry run -> recording -> mix -> review.png
```

`make.sh` prints one line per step with its timing, then the review: one frame per step in `out/review.png` and the gap between each step and its voice onset (normally ~0.1 s). If a target can't be found it stops with the step, the target and `out/failure.png`, plus the closest visible texts ("did you mean …").

Useful partial runs:

```bash
python3 draft.py https://app.example.com out            # no scenario yet: reads the page, writes out/draft-scenario.txt to edit
python3 scenario.py scenario.txt                        # show the parsed JSON (checks the syntax)
python3 tts.py --preview "One line" out fr-fr           # the same line in every French voice -> out/voices-preview.mp3
node record.js scenario.txt out --dry                   # check every target without recording
python3 mix.py out/scenario.json out demo.mp4           # re-mix only (captions, music, cards changed)
python3 check.py out demo.mp4                           # rebuild review.png + sync report
```

Outputs in `out/`: `demo.mp4`, `captions.srt`, `review.png`, `explore.png`, `explore.json`, `scenario.json`, `voice.wav`, `frames/`, and `demo.gif` when `gif: yes`.

## How it works

1. **Narration first** — `tts.py` rewrites each line for speech (URLs, prices, units, symbols, `pronounce` map), synthesises one clip per step, polishes it (silence trim, high-pass, presence EQ, compression, −16 LUFS) and measures its length.
2. **Record to the voice's timing** — `record.js` plays the steps with Playwright and holds each step at least as long as its narration. Frames come from the Chrome DevTools screencast, timestamped on the same clock as the steps, so audio and video stay in sync within ~50 ms. The cursor eases along a gentle arc between targets; it, the ripples, highlights and callouts are drawn through the CSSOM, so they also work on sites with a strict Content-Security-Policy.
3. **Mix** — `mix.py` places each clip at its step's start, burns in captions and chapter labels (ASS, Inter font), draws the frame, the title / section / recap / outro cards, QR code and progress bar, ducks the music under the voice and encodes H.264 MP4.
4. **Review** — `check.py` extracts one frame per step into a contact sheet and compares voice onsets to step starts.

## Voices

| Engine | Notes |
|---|---|
| `kokoro` (default) | Free, runs locally, no API key. 50+ voices in 9 languages, blendable (`af_heart*0.7+af_sky*0.3`). |
| `openai` | `OPENAI_API_KEY`, natural in French/English, tone via `instructions`. |
| `elevenlabs` | `ELEVENLABS_API_KEY`, best quality, voice cloning. |
| `none` | Silent video, captions only. |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `playwright install` hangs or fails | The browser CDN is blocked. `setup.sh` already falls back to a portable Chromium; or set `CHROMIUM_PATH=/path/to/chrome`. |
| Page looks unstyled in `explore.png` | Its CSS/JS CDN is unreachable from this network. `record.js` prints a `note:` with the blocked hosts. Record from another network. |
| `the site answered with a bot check` | Cloudflare / "Client Challenge" / CAPTCHA. Not bypassed on purpose. Use direct URLs (`> go to …`) instead of the site's search, a `login state` file, or a network the site trusts. |
| `can't find "…"` with did-you-mean suggestions | Use the exact visible text from `--explore`, add `#2`, or a CSS selector. |
| Voice starts before the page is ready | Add `> wait for "…"` on the element the narration talks about. |
| Chromium behind a corporate proxy | `HTTPS_PROXY=http://user:pass@host:port` is passed to the browser; or set `DEMO_PROXY`. |
| ffmpeg errors about `rate` or sample formats | ffmpeg < 4.4. Upgrade, or `brew install ffmpeg` / `apt install ffmpeg`. |
| French/other Kokoro voice sounds flat | Kokoro is best in English; use `engine: openai` or `elevenlabs` for other languages. |

## License

MIT
