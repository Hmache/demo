---
name: demo-video
description: Record a narrated product demo video of a website — opens the given URL in a browser, plays the user's scenario written in plain text (clicks, typing, scrolling) and renders an MP4 with AI voice-over and captions.
---

# Demo video

Turn **a URL + a scenario in plain text** into a polished MP4: headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in, and optional background music is ducked under the voice.

The voice drives the timing: each narration clip is generated **first**, then the recorder holds every step at least as long as its line. Frames are captured with the CDP screencast, which timestamps every frame on the same clock as the steps, so the voice lands on the right action.

## 1. Gather inputs (use sensible defaults, don't over-ask)

| Input | Default |
|---|---|
| URL | required |
| Scenario | required — free words from the user, or a `scenario.txt` they wrote in the format below |
| Narration language / voice | same language as the user's request; Kokoro `af_heart` (en) / `ff_siwis` (fr) |
| Resolution | 1920×1080 (use 1280×720 for quick drafts or GIFs) |
| Captions | on |
| Music | off (on only if the user supplies a file) |
| Login | none; if the app needs one, ask for test credentials or a Playwright `storageState` file — never store credentials in the skill or in memory |

Ask with AskUserQuestion only when the URL or scenario is missing, or a login is clearly needed. Otherwise go.

**Where it runs.** Default: the cloud workspace (Chromium is preinstalled). If the URL is `localhost`, a LAN/VPN host, or blocked by the egress proxy (curl returns 403/000), run the whole pipeline on the user's computer with `device_bash` instead (setup.sh installs Playwright + Chromium there), writing the output into their connected folder.

## 2. Install the toolkit (once per session)

The scripts ship next to this SKILL.md (`setup.sh`, `make.sh`, `scenario.py`, `tts.py`, `record.js`, `mix.py`). Copy them and run setup:

```bash
mkdir -p ~/.cache/demo-video/bin && cp <this skill's folder>/{setup.sh,make.sh,scenario.py,tts.py,record.js,mix.py} ~/.cache/demo-video/bin/
chmod +x ~/.cache/demo-video/bin/*.sh && ~/.cache/demo-video/bin/setup.sh
```

Skip if `~/.cache/demo-video/bin/scenario.py` already exists.

## 3. The scenario is a plain-text file

Write (or take the user's) `scenario.txt`. Settings go at the top, then one block per step separated by blank lines. In a block, normal lines are the **narration** (spoken + captioned), lines starting with `>` are the **actions**.

```text
url: https://app.example.com
voice: af_heart
size: 1920x1080

Here's the dashboard: every order from the last 30 days in one place.

Let's find a customer by name.
> type "Dupont" into "Search"
> press Enter
> wait for "Order history"

One click opens the full order history.
> click "Dupont SARL"

Filters narrow thousands of orders down in a second.
> select "Last 7 days" in "Period"
> scroll down
```

**Actions** (one per `>` line):

| Action | Example |
|---|---|
| click | `> click "Sign in"` · `> click checkbox #2` · `> click "Save" #2` (2nd match) |
| hover | `> hover over "Pricing"` |
| type (visible typing) | `> type "hello" into "Message"` · `> type "hello"` (focused field) |
| fill (instant) | `> fill "Email" with "demo@acme.com"` |
| select | `> select "France" in "Country"` |
| press a key | `> press Enter` · `> press Tab` · `> press Meta+K` |
| scroll | `> scroll down` · `> scroll up 300` · `> scroll to "Testimonials"` |
| wait | `> wait 2s` · `> wait for "Results"` |
| open a page | `> go to https://app.example.com/settings` |
| run JS | `> js: document.querySelector('.cookie-banner')?.remove()` |

**Targets** are what the viewer sees: a button or link label, a field's placeholder or label, or any visible text. `#N` picks the N-th match; a bare role word (`checkbox`, `button`, `link`, `textbox`…) picks by role. A CSS selector (`.toggle`, `#save`, `input[name=q]`) also works when text is ambiguous. Page loads after a click or Enter are detected automatically.

**Settings** (all optional except `url`): `voice`, `engine` (kokoro / openai / elevenlabs / none), `lang`, `speed`, `size`, `captions` (yes/no), `music` (path to mp3), `music volume` (0.25), `gif` (yes/no), `locale`, `typing speed` (ms per char, 55), `pause` (silence after each line, 0.6 s), `login state` (Playwright storageState file), `model`, `instructions` (OpenAI voice tone). Lines starting with `//` are comments.

The scripts also accept the JSON form (`python3 scenario.py scenario.txt` shows it).

**Voices**:
- `kokoro` — default, free, local, no key. English: `af_heart`, `af_bella`, `am_michael`, `am_fenrir`, `bf_emma`, `bm_george`. French: only `ff_siwis` (lang set automatically) — fine for drafts.
- `openai` — needs `OPENAI_API_KEY`; voices alloy, ash, coral, sage, verse…; `instructions: warm, confident product demo`. Natural in French.
- `elevenlabs` — needs `ELEVENLABS_API_KEY`; `voice` = voice ID. Best quality, voice cloning.
- `none` — silent video (captions still shown).
Ask the user for a key only when they want OpenAI/ElevenLabs; pass it as an env var for that command only, never write it to a file.

**Writing the narration** (when the user gave free words): one or two short spoken sentences per step (6–20 words), say *why it matters* rather than narrating clicks ("Filters narrow thousands of orders down in a second", not "I click the filter button"). First step = intro while the page sits still; last step = short takeaway. Put the action the voice describes in the same block. Save the file and show it to the user with the video — it's the editable source.

## 4. Check targets before recording

```bash
export NODE_PATH=$(npm root -g)
node ~/.cache/demo-video/bin/record.js scenario.txt out --explore=0   # page at start
node ~/.cache/demo-video/bin/record.js scenario.txt out --explore=3   # after the first 3 steps
```

Explore prints every visible button, link and field with its text, and saves `out/explore.png` — Read it. Use the exact visible text in the scenario. The dry run in step 5 then checks every target quickly.

## 5. Render

```bash
~/.cache/demo-video/bin/make.sh scenario.txt out /mnt/user-data/outputs/<name>.mp4
```

It runs parse → narration → dry run (checks every target fast) → recording → mix. If a step fails, it prints the step, the target it couldn't find and saves `out/failure.png`: Read it, fix the target or add a `> wait for`, rerun. Re-render only the mix (e.g. captions/music change) with `python3 ~/.cache/demo-video/bin/mix.py out/scenario.json out <file>.mp4`.

## 6. Review your own video before delivering (mandatory)

1. For each step, extract a frame ~1 s after its start (`out/timing.json` start − trimStart) with `ffmpeg -ss T -i video.mp4 -frames:v 1 check_N.png` and Read them: right screen, cursor visible, caption readable, no cookie banner / modal / spinner hiding the content.
2. Check voice sync: `ffmpeg -i video.mp4 -af silencedetect=n=-40dB:d=0.3 -f null - 2>&1 | grep silence_end` — voice onsets should match step starts within ~0.1 s.
3. Watch for: blank/white first frames, page still loading when the voice talks about it (add `> wait for`), dead time > 3 s (remove a `> wait`), typing too slow (`typing speed: 35`), captions over important UI (`> scroll down`).
Fix and re-render until clean — don't hand over a video with visible problems.

## 7. Deliver

- The MP4 in `/mnt/user-data/outputs/` (plus the GIF if asked) and the `scenario.txt`. If a folder is connected, also commit them there.
- Mention `out/captions.srt` for YouTube/LinkedIn uploads, and that editing `scenario.txt` and re-running regenerates the video.
- One-line summary: duration, resolution, voice used. Offer tweaks (voice, pace, wording, music).
