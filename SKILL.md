---
name: demo-video
description: Record a narrated product demo video of a website — opens the given URL in a browser, plays the user's scenario (clicks, typing, scrolling) and renders an MP4 with AI voice-over and captions.
---

# Demo video

Turn **a URL + a scenario in plain words** into a polished MP4: headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in, and optional background music is ducked under the voice.

The voice drives the timing: each narration clip is generated **first**, then the recorder holds every step at least as long as its line. Frames are captured with the CDP screencast, which timestamps every frame on the same clock as the steps, so the voice lands on the right action.

## 1. Gather inputs (use sensible defaults, don't over-ask)

| Input | Default |
|---|---|
| URL | required |
| Scenario (what to show, in order) | required |
| Narration language / voice | same language as the user's request; Kokoro `af_heart` (en) / `ff_siwis` (fr) |
| Resolution | 1920×1080 (use 1280×720 for quick drafts or GIFs) |
| Captions | on |
| Music | off (on only if the user supplies a file) |
| Login | none; if the app needs one, ask for test credentials or a Playwright `storageState` file — never store credentials in the skill or in memory |

Ask with AskUserQuestion only when the URL or scenario is missing, or a login is clearly needed. Otherwise go.

**Where it runs.** Default: the cloud workspace (Chromium is preinstalled). If the URL is `localhost`, a LAN/VPN host, or blocked by the egress proxy (curl returns 403/000), run the whole pipeline on the user's computer with `device_bash` instead (setup.sh installs Playwright + Chromium there), writing the output into their connected folder.

## 2. Install the toolkit (once per session)

The scripts ship next to this SKILL.md (`setup.sh`, `make.sh`, `tts.py`, `record.js`, `mix.py`). Copy them and run setup:

```bash
mkdir -p ~/.cache/demo-video/bin && cp <this skill's folder>/{setup.sh,make.sh,tts.py,record.js,mix.py} ~/.cache/demo-video/bin/
chmod +x ~/.cache/demo-video/bin/*.sh && ~/.cache/demo-video/bin/setup.sh
```

Skip if `~/.cache/demo-video/bin/make.sh` already exists.

## 3. Explore the page before writing selectors

Guessed selectors are the #1 failure. Create a work dir (e.g. `~/demos/<slug>/`) and a first `scenario.json` with just the URL and `"steps": []`, then:

```bash
export NODE_PATH=$(npm root -g)
node ~/.cache/demo-video/bin/record.js scenario.json out --explore=0
```

It prints the visible interactive elements with ready-to-use selectors and saves `out/explore.png` — Read the screenshot. For multi-page flows, write the first steps, then `--explore=N` fast-runs steps 0..N-1 and dumps the page you land on. Repeat until every step has a verified selector.

Selector preferences: `#id` > `[data-testid=…]` > `input[placeholder="…"]` / `[aria-label="…"]` > `button:has-text('…')` > `text=…`. Append `>> nth=K` when several match.

## 4. Write scenario.json

```json
{
  "url": "https://app.example.com",
  "viewport": {"width": 1920, "height": 1080},
  "voice": {"engine": "kokoro", "voice": "af_heart", "lang": "en-us", "speed": 1.0},
  "captions": true,
  "steps": [
    {"say": "Here's the dashboard — every order from the last 30 days in one place.", "actions": []},
    {"say": "Let's find a customer by name.", "actions": [
      {"type": "click", "selector": "input[placeholder=\"Search\"]"},
      {"type": "type", "selector": "input[placeholder=\"Search\"]", "text": "Dupont"},
      {"type": "press", "key": "Enter"},
      {"type": "waitFor", "selector": ".results"}]},
    {"say": "One click opens the full order history.", "actions": [
      {"type": "click", "selector": ".results li >> nth=0", "navigates": true}]}
  ]
}
```

**Actions**: `goto {url}` · `click {selector, navigates?}` · `hover {selector, ms?}` · `type {selector, text, clear?, delay?}` (visible typing) · `fill {selector, text}` (instant) · `select {selector, value}` · `press {key, navigates?}` · `scroll {y}` or `scroll {selector, offset?}` (smooth) · `moveTo {x, y}` · `wait {ms}` · `waitFor {selector, state?, timeout?}` · `waitForUrl {url}` · `eval {js}` (e.g. dismiss a cookie banner, highlight an element).
Set `navigates: true` on a click/press that loads a new page.

**Optional keys**: `music` (path to mp3), `musicVolume` (0.25), `gif` (true → also a GIF), `gapAfterVoice` (0.6 s), `minStepHold` (1.5 s for silent steps), `typeDelay` (55 ms/char), `outroHold` (1 s), `fps` (30), `crf` (18), `jpegQuality` (92), `locale`, `storageState`, `httpCredentials {username, password}`, `captionFont` ("Inter").

**Voice engines** (`voice.engine`):
- `kokoro` — default, free, local, no key. English voices: `af_heart`, `af_bella`, `am_michael`, `am_fenrir`, `bf_emma`, `bm_george` (lang `en-us` / `en-gb`). French: only `ff_siwis` (lang `fr-fr`) — fine for drafts.
- `openai` — needs `OPENAI_API_KEY`; `voice`: alloy, ash, coral, sage, verse…; `model` gpt-4o-mini-tts; `instructions` for tone ("warm, confident product demo"). Natural in French.
- `elevenlabs` — needs `ELEVENLABS_API_KEY`; `voice` = voice ID; `model` eleven_multilingual_v2. Best quality, voice cloning.
- `none` — silent video (captions still work if `say` is set).
Ask the user for a key only when they want OpenAI/ElevenLabs; pass it as an env var for that command only, never write it to a file.

**Writing the narration** (`say`): one line per step, 6–20 words, spoken style, say *why it matters* rather than narrating clicks ("Filters narrow thousands of orders down in a second", not "I click the filter button"). First step = intro while the page sits still; last step = short takeaway. Put the action the voice describes in the same step. Long actions (typing a long text) are fine — the step lasts max(actions, voice).

## 5. Render

```bash
~/.cache/demo-video/bin/make.sh scenario.json out /mnt/user-data/outputs/<name>.mp4
```

It runs narration → dry run (checks every selector fast) → recording → mix. If a step fails, it prints the step and saves `out/failure.png`: Read it, fix the selector or add a `waitFor`, rerun. Re-render only the mix (e.g. captions/music change) with `python3 ~/.cache/demo-video/bin/mix.py scenario.json out <file>.mp4`.

## 6. Review your own video before delivering (mandatory)

1. For each step, extract a frame ~1 s after its start (`out/timing.json` start − trimStart) with `ffmpeg -ss T -i video.mp4 -frames:v 1 check_N.png` and Read them: right screen, cursor visible, caption readable, no cookie banner / modal / spinner hiding the content.
2. Check voice sync: `ffmpeg -i video.mp4 -af silencedetect=n=-40dB:d=0.3 -f null - 2>&1 | grep silence_end` — voice onsets should match step starts within ~0.1 s.
3. Watch for: blank/white first frames, page still loading when the voice talks about it (add `waitFor`), dead time > 3 s (trim a `wait`), text typed too slowly (raise speed with `delay`), captions over important UI (scroll content up).
Fix and re-render until clean — don't hand over a video with visible problems.

## 7. Deliver

- The MP4 in `/mnt/user-data/outputs/` (plus the GIF if asked). If a folder is connected, also commit it there.
- Mention that `out/captions.srt` exists for YouTube/LinkedIn uploads and that `scenario.json` can be edited and re-rendered.
- One-line summary: duration, resolution, voice used. Offer tweaks (voice, pace, wording, music).
