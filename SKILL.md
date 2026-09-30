---
name: demo-video
description: Record a narrated product demo video of a website — opens the given URL in a browser, plays the user's scenario written in plain text (clicks, typing, scrolling) and renders an MP4 with AI voice-over and captions.
---

# Demo video

Turn **a URL + a scenario in plain text** into a polished MP4: headless Chromium plays the scenario with a visible animated cursor and click ripples, an AI voice narrates each step, captions are burned in, and the production layer makes it look like a studio demo: title, section and outro cards with crossfades, a framed browser on a brand-tinted background, chapter labels, a presenter bubble with your photo and live voice bars, logo watermark, spotlight highlights, zooms, callouts, key badges, a progress bar, a QR code on the outro and ducked background music (generated if you have none).

The voice drives the timing: each narration clip is generated **first**, then the recorder holds every step at least as long as its line. Frames are captured with the CDP screencast, which timestamps every frame on the same clock as the steps, so the voice lands on the right action.

## 1. Gather inputs (use sensible defaults, don't over-ask)

| Input | Default |
|---|---|
| URL | required |
| Scenario | required — free words from the user, or a `scenario.txt` they wrote in the format below |
| Narration language / voice | same language as the user's request; Kokoro `af_heart` (en) / `ff_siwis` (fr) |
| Resolution | 1920×1080 (`size: mobile` for a phone demo; 1280×720 for quick drafts or GIFs) |
| Captions, progress bar, click highlights, key badges | on |
| Template | `template: launch` (framed, chapters, transitions) unless the user wants raw screen (`walkthrough`), a phone (`mobile`), a vertical social clip (`social`) or nothing extra (`minimal`) |
| Title / section / outro cards | on: product name + tagline, one `## Section` per part of the demo, a call-to-action outro with a QR code when there is a URL |
| Presenter photo, logo | only if the user provides the files (ask once, in the same question as the URL/scenario); the presenter pill stays off unless they ask for it |
| Music | `music: auto` (a soft generated ambient bed, ducked under the voice) unless the user supplies a track or says no music |
| Login | none; if the app needs one, ask for test credentials or a Playwright `storageState` file — never store credentials in the skill or in memory |

Ask with AskUserQuestion only when the URL or scenario is missing, or a login is clearly needed. Otherwise go.

**Where it runs.** Default: the cloud workspace (Chromium is preinstalled). If the URL is `localhost`, a LAN/VPN host, or blocked by the egress proxy (curl returns 403/000), run the whole pipeline on the user's computer with `device_bash` instead, writing the output into their connected folder. There, `setup.sh` installs Playwright locally and, when Playwright's browser CDN is blocked, fetches a portable ungoogled-chromium from GitHub and stubs any missing X library; `make.sh` picks it up automatically. Keep every `device_bash` call under its time limit: run `tts.py`, `record.js` and `mix.py` as separate calls for long demos.

**Real-site lessons** (already handled by the scripts, but know them): sites with a strict Content-Security-Policy are fine (the overlay uses the CSSOM, never injected stylesheets); a proxy with credentials in `HTTPS_PROXY` is passed to the browser; the recorder prints a `note:` listing hosts that were blocked — if the page looks unstyled in `explore.png`, its CSS/JS CDN is unreachable and a different network is needed; a bot check ("Client Challenge", CAPTCHA) stops the run with a clear error — never try to solve it; use direct URLs (`> go to …`) instead of a site's search, or a `login state`.

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
template: launch
voice: af_heart
title: Acme Orders
subtitle: Every order, one screen
outro: Try it free at acme.com
qr: https://acme.com/signup
brand color: #2563eb
logo: acme-logo.png
music: auto
cookies: dismiss

## The dashboard

# Everything in one place
Here's the dashboard: every order from the last 30 days in one place.

# Find a customer
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

**Structure lines**: `## Title` on its own block = a full-screen section card (2.2 s, crossfaded); `# Title` as the first line of a step = a chapter label shown top-left for 3 s (numbered automatically). Use 2–4 sections for anything over a minute; every step should have a label in `launch`/`walkthrough` templates.

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
- Template: `template: launch | walkthrough | social | mobile | minimal` sets sensible bundles (size, frame, chapters, transitions); any setting written after it overrides.
- Look: `size` (`1920x1080`, or a preset: `mobile`, `tablet`, `desktop`, `square`, `vertical`), `hd: yes` (retina-sharp, output = 2× the size; slower encode), `frame: yes` (browser floats with rounded corners and a shadow on a gradient tinted with the brand colour; captions sit below it), `title` + `subtitle` (2.5 s intro card), `outro` (closing card — the call-to-action) + `qr: https://…` (QR code under it), `transitions: yes` (0.5 s crossfades between cards and the recording), `brand color` (#hex for the gradient, labels, callouts, highlights and progress bar), `logo: file.png` (watermark, bottom-right), `presenter: bubble` + `photo: me.jpg` (opt-in, off in every template: a pill with the presenter's photo and voice-reactive bars, bottom-left of the recording — it covers part of the page, so only add it when the user asks for it), `chapters` (yes/no: the `#` labels), `progress bar` (yes/no), `highlight clicks` (yes/no: spotlight ring on each click target), `show keys` (yes/no: a badge like `⌘ + K` on every `> press`), `captions` (yes/no), `font` (caption font), `gif` (yes/no). On `size: mobile` the cursor becomes a touch dot.
- Behaviour: `cookies: dismiss` (auto-dismiss banners after every page load), `typing speed` (ms per char, 55), `pause` (silence after each line, 0.6 s), `locale`, `login state` (Playwright storageState file).
- Secrets: text in `type`/`fill` can use `$NAME` — it is read from the environment when rendering, so a login step is `> fill "Email" with "$DEMO_USER"` + `> fill "Password" with "$DEMO_PASS"` and the render command is `DEMO_USER=… DEMO_PASS=… make.sh …`. Ask the user for test credentials in chat, pass them only on that command line, never write them in the scenario, the skill or memory. Password fields show dots on screen anyway.
- Voice: `voice`, `engine` (kokoro / openai / elevenlabs / none), `lang`, `speed` (0.95 = calm demo pace), `pronounce` (`Parla=Par-la, Weepo=Wee-po` — how brand names are spoken), `polish` (yes/no: the audio chain below), `sentence pause` (0.35 s), `music` (path to an mp3, or `auto` for a generated soft ambient bed — always ducked under the voice), `music volume` (0.25), `model`, `instructions` (OpenAI voice tone), `stability` / `style` (ElevenLabs).
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

**Shape of a good demo** (45–90 s, 5–8 steps): title card → one-line hook while the page sits still → 2–4 `## sections`, each with 1–3 labelled steps that show one outcome (the strongest first) → a closing line with the takeaway → outro card with the call-to-action and QR code. This is the same structure the commercial demo makers (Synthesia-style templates) use: scene cards, a presenter, lower-thirds, brand kit, music, CTA. Use `zoom into` for a number or detail that would be too small to read, `highlight` for the one control the viewer must notice, and `> wait 1s` after a result appears so it can be read. Avoid more than one zoom per step and never zoom during typing. Use `callout` for a benefit the screen doesn't state ("Synced in real time"), at most one or two per demo. **Several languages**: copy the scenario, translate only the narration lines, `title`/`subtitle`/`outro`, and set `voice`/`lang` — the actions stay identical.

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
- Offer the two things this pipeline cannot do locally, if the user asks for them: a photorealistic talking avatar (needs a hosted service such as HeyGen/D-ID/Synthesia — the presenter bubble is the local stand-in) and studio voices (OpenAI/ElevenLabs engines with a key).
- Mention `out/captions.srt` for YouTube/LinkedIn uploads, and that editing `scenario.txt` and re-running regenerates the video.
- One-line summary: duration, resolution, voice used. Offer tweaks (voice, pace, wording, music).
