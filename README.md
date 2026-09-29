# demo-video

Turn **a URL + a scenario in plain words** into a narrated product demo video.

Headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in, and optional background music is ducked under the voice. Output: MP4 (+ optional GIF and `.srt` captions).

Built as an agent skill (`SKILL.md`), but the scripts work on their own too.

## How it works

1. **Narration first** — `tts.py` generates one voice clip per step and measures its length.
2. **Record to the voice's timing** — `record.js` plays the steps with Playwright and holds each step at least as long as its narration. Frames come from the Chrome DevTools screencast, timestamped on the same clock as the steps, so audio and video stay in sync (within ~50 ms).
3. **Mix** — `mix.py` places each clip at its step's start, burns in captions (Inter), optionally ducks music, and encodes H.264 MP4.

## Quick start

```bash
./setup.sh                                   # Playwright, Kokoro TTS model, Inter font (idempotent)
node record.js scenario.json out --explore=0 # list clickable elements + screenshot, to pick selectors
./make.sh scenario.json out demo.mp4         # narration -> dry run -> recording -> mix
```

Requirements: Node 18+, Python 3.10+, ffmpeg.

## Scenario format

See [`example-scenario.json`](example-scenario.json). Each step has a `say` line (narration + caption) and a list of `actions`:

`goto` · `click` · `hover` · `type` (visible typing) · `fill` · `select` · `press` · `scroll` · `moveTo` · `wait` · `waitFor` · `waitForUrl` · `eval`

## Voices

| Engine | Notes |
|---|---|
| `kokoro` (default) | Free, runs locally, no API key. Great in English; one French voice (`ff_siwis`). |
| `openai` | `OPENAI_API_KEY`, natural in French/English, tone via `instructions`. |
| `elevenlabs` | `ELEVENLABS_API_KEY`, best quality, voice cloning. |
| `none` | Silent video, captions only. |

## Optional settings

`music`, `musicVolume`, `gif`, `gapAfterVoice`, `minStepHold`, `typeDelay`, `outroHold`, `fps`, `crf`, `jpegQuality`, `locale`, `storageState` (logged-in session), `httpCredentials`, `captionFont`.

## License

MIT
