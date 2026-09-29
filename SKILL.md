---
name: demo-video
description: Record a narrated product demo video of a website — opens the given URL in a browser, plays the user's scenario written in plain text (clicks, typing, scrolling) and renders an MP4 with AI voice-over and captions.
---

# Demo video

Turn **a URL + a scenario in plain text** into a polished MP4: headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in, and optional title/outro cards, a framed browser on a brand-tinted background, spotlight highlights, zooms, callouts, key badges, a progress bar and ducked background music finish it.

The voice drives the timing: each narration clip is generated **first**, then the recorder holds every step at least as long as its line. Frames are captured with the CDP screencast, which timestamps every frame on the same clock as the steps, so the voice lands on the right action.

## 1. Gather inputs (use sensible defaults, don't over-ask)

| Input | Default |
|---|---|
| URL | required |
| Scenario | required — free words from the user, or a `scenario.txt` they wrote in the format below |
| Narration language / voice | same language as the user's request; Kokoro `af_heart` (en) / `ff_siwis` (fr) |
| Resolution | 1920×1080 (`size: mobile` for a phone demo; 1280×720 for quick drafts or GIFs) |
| Captions, progress bar, click highlights, key badges | on |
| Frame (browser floating on a gradient) | on for desktop and phone demos; off when the user wants raw full-frame screen |
| Title / outro cards | on when the product name and a call-to-action are known or obvious from the site |
| Music | off (on only if the user supplies a file) |
| Login | none; if the app needs one, ask for test credentials or a Playwright `storageState` file — never store credentials in the skill or in memory |

Ask with AskUserQuestion only when the URL or scenario is missing, or a login is clearly needed. Otherwise go.

**Where it runs.** Default: the cloud workspace (Chromium is preinstalled). If the URL is `localhost`, a LAN/VPN host, or blocked by the egress proxy (curl returns 403/000), run the whole pipeline on the user's computer with `device_bash` instead (setup.sh installs Playwright + Chromium there), writing the output into their connected folder.

## 2. Install the toolkit (once per session)

The scripts ship next to this SKILL.md (`setup.sh`, `make.sh`, `scenario.py`, `tts.py`, `record.js`, `mix.py`, `check.py`). Copy them and run setup:

```bash
mkdir -p ~/.cache/demo-video/bin && cp <this skill's folder>/{setup.sh,make.sh,scenario.py,tts.py,record.js,mix.py,check.py} ~/.cache/demo-video/bin/
chmod +x ~/.cache/demo-video/bin/*.sh && ~/.cache/demo-video/bin/setup.sh
```

Skip if `~/.cache/demo-video/bin/check.py` already exists.

## 3. The scenario is a plain-text file

Write (or take the user's) `scenario.txt`. Settings go at the top, then one block per step separated by blank lines. In a block, normal lines are the **narration** (spoken + captioned), lines starting with `>` are the **actions**.

```text
url: https://app.example.com
voice: af_heart
size: 1920x1080
title: Acme Orders
subtitle: Every order, one screen
outro: Try it free at acme.com
brand color: #2563eb
frame: yes
cookies: dismiss
highlight clicks: yes
progress bar: yes

Here's the dashboard: every order from the last 30 days in one place.

Let's find a customer by name.
> type "Dupont" into "Search"
> press Enter
> wait for "Order history"

One click opens the full order history.
> click "Dupont SARL"
> callout "Loads in under a second" at "Order history"

Filters narrow thousands of orders down in a second.
> select "Last 7 days" in "Period"
> zoom into "Total revenue" x2
> wait 1s
> zoom out

Everything ends up in one place: the customer's history.
> highlight "Order history"
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
| highlight (spotlight ring, rest dimmed) | `> highlight "Export"` · `> highlight "Total" for 3s` |
| zoom | `> zoom into "Revenue chart"` · `> zoom into "Total" x2.5` · `> zoom out` |
| callout (floating label above an element) | `> callout "Synced in real time" at "Status"` · `… for 3s` |
| cookie banner | `> dismiss cookies` (clicks a decline/only-necessary button, else hides the banner) |
| wait | `> wait 2s` · `> wait for "Results"` |
| open a page | `> go to https://app.example.com/settings` |
| run JS | `> js: document.querySelector('.cookie-banner')?.remove()` |

**Targets** are what the viewer sees: a button or link label, a field's placeholder or label, or any visible text. `#N` picks the N-th match; a bare role word (`checkbox`, `button`, `link`, `textbox`…) picks by role. A CSS selector (`.toggle`, `#save`, `input[name=q]`) also works when text is ambiguous. Page loads after a click or Enter are detected automatically.

**Settings** (all optional except `url`):
- Look: `size` (`1920x1080`, or a preset: `mobile`, `tablet`, `desktop`, `square`, `vertical`), `hd: yes` (retina-sharp, output = 2× the size; slower encode), `frame: yes` (browser floats with rounded corners and a shadow on a gradient tinted with the brand colour; captions sit below it), `title` + `subtitle` (2.5 s intro card), `outro` (3 s closing card — the call-to-action), `brand color` (#hex for the gradient, subtitle, callouts, highlights and progress bar), `progress bar` (yes/no), `highlight clicks` (yes/no: spotlight ring on each click target), `show keys` (yes/no: a badge like `⌘ + K` on every `> press`), `captions` (yes/no), `gif` (yes/no). On `size: mobile` the cursor becomes a touch dot.
- Behaviour: `cookies: dismiss` (auto-dismiss banners after every page load), `typing speed` (ms per char, 55), `pause` (silence after each line, 0.6 s), `locale`, `login state` (Playwright storageState file).
- Secrets: text in `type`/`fill` can use `$NAME` — it is read from the environment when rendering, so a login step is `> fill "Email" with "$DEMO_USER"` + `> fill "Password" with "$DEMO_PASS"` and the render command is `DEMO_USER=… DEMO_PASS=… make.sh …`. Ask the user for test credentials in chat, pass them only on that command line, never write them in the scenario, the skill or memory. Password fields show dots on screen anyway.
- Voice: `voice`, `engine` (kokoro / openai / elevenlabs / none), `lang`, `speed` (0.95 = calm demo pace), `pronounce` (`Parla=Par-la, Weepo=Wee-po` — how brand names are spoken), `polish` (yes/no: the audio chain below), `sentence pause` (0.35 s), `music` (path to mp3, ducked under the voice), `music volume` (0.25), `model`, `instructions` (OpenAI voice tone), `stability` / `style` (ElevenLabs).
Lines starting with `//` are comments.

The scripts also accept the JSON form (`python3 scenario.py scenario.txt` shows it).

**Voices**:
- `kokoro` — default, free, local, no key. English (US): `af_heart` (warm, default), `af_bella`, `af_nova`, `af_sky`, `am_michael`, `am_fenrir`, `am_puck`, `am_onyx` (deep). English (UK): `bf_emma`, `bf_isabella`, `bm_george`, `bm_daniel`. French `ff_siwis`; Spanish `ef_dora`/`em_alex`; Italian `if_sara`/`im_nicola`; Portuguese `pf_dora`/`pm_alex`; Japanese `jf_alpha`; Chinese `zf_xiaoxiao`; Hindi `hf_alpha`. The language is set from the voice prefix automatically. **Blends** make a voice unique: `voice: af_heart*0.7+af_sky*0.3`.
- `openai` — needs `OPENAI_API_KEY`; voices alloy, ash, coral, sage, verse…; `instructions: warm, confident product demo`. Natural in French.
- `elevenlabs` — needs `ELEVENLABS_API_KEY`; `voice` = voice ID; `stability: 0.5`, `style: 0.2`. Best quality, voice cloning.
- `none` — silent video (captions still shown).
Ask the user for a key only when they want OpenAI/ElevenLabs; pass it as an env var for that command only, never write it to a file.

**What happens to the voice automatically** (all engines): the narration is rewritten for speech before synthesis — `acme.com/pricing` → "acme dot com slash pricing", `$49/month` → "49 dollars per month", `20%` → "20 percent", `2s` → "2 seconds", `v2.5` → "version 2 point 5", `→` → "then", `⌘+K` → "command K", plus the `pronounce` map — and every clip is silence-trimmed, high-passed, given a little presence, lightly compressed and loudness-normalised to −16 LUFS, so clips sound even and "produced" and background music sits under them. Write the narration as it should be *read* (digits, symbols are fine); write brand names in `pronounce` if the first render mispronounces them.

**Let the user hear the options**: `python3 ~/.cache/demo-video/bin/tts.py --preview "One line from the demo" out fr-fr` writes `out/voices-preview.mp3` — the same line in every recommended voice for that language, each announced by name. Send it when the user asks which voice to use, or when the language has several candidates.

**Writing the narration** (when the user gave free words): one or two short spoken sentences per step (6–20 words), say *why it matters* rather than narrating clicks ("Filters narrow thousands of orders down in a second", not "I click the filter button"). First step = intro while the page sits still; last step = short takeaway. Put the action the voice describes in the same block. Save the file and show it to the user with the video — it's the editable source.

**Shape of a good demo** (45–90 s, 5–8 steps): title card → one-line hook while the page sits still → 3–5 steps that each show one outcome (the strongest first) → a closing line with the takeaway → outro card with the call-to-action. Use `zoom into` for a number or detail that would be too small to read, `highlight` for the one control the viewer must notice, and `> wait 1s` after a result appears so it can be read. Avoid more than one zoom per step and never zoom during typing. Use `callout` for a benefit the screen doesn't state ("Synced in real time"), at most one or two per demo. **Several languages**: copy the scenario, translate only the narration lines, `title`/`subtitle`/`outro`, and set `voice`/`lang` — the actions stay identical.

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

`make.sh` ends by running `check.py`, which writes `out/review.png` (one frame per step, labelled) and prints the voice-sync report. **Read `out/review.png`** and check every frame: right screen, cursor on the right element, caption readable, no cookie banner / modal / spinner hiding the content, zooms centred on the thing being described. Then read the report: every step's voice should start within ~0.15 s of the step; a `WARNING` or `NO voice onset` line means something is off.

Voice checks: read the printed spoken text (`step N: … <spoken>`) for anything that would sound wrong — a brand name, an acronym, a number — and fix it with `pronounce` or by rewording; a step whose voice lasts more than ~7 s should be split.

Common fixes: page still loading when the voice talks about it → `> wait for "…"`; dead time > 3 s → remove a `> wait` or shorten the line; typing too slow → `typing speed: 35`; captions over important UI → `> scroll down`; a zoom that shows blank space → smaller factor (`x1.5`). Fix and re-render until clean — don't hand over a video with visible problems. Re-run only the review with `python3 ~/.cache/demo-video/bin/check.py out <file>.mp4`.

## 7. Deliver

- The MP4 in `/mnt/user-data/outputs/` (plus the GIF if asked) and the `scenario.txt`. If a folder is connected, also commit them there.
- Mention `out/captions.srt` for YouTube/LinkedIn uploads, and that editing `scenario.txt` and re-running regenerates the video.
- One-line summary: duration, resolution, voice used. Offer tweaks (voice, pace, wording, music).
