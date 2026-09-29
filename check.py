#!/usr/bin/env python3
"""Self-review helper: one frame per step in a labelled contact sheet + voice-sync report.

Usage: python3 check.py OUT_DIR [video.mp4]
Writes OUT_DIR/review.png (look at it!) and prints, per step, start time, caption and the
gap between the step start and the first voice onset.
"""
import json, os, re, subprocess, sys

OUT = sys.argv[1]
VIDEO = sys.argv[2] if len(sys.argv) > 2 else os.path.join(OUT, "demo.mp4")
timing = json.load(open(f"{OUT}/timing.json"))
sc = json.load(open(f"{OUT}/scenario.json")) if os.path.exists(f"{OUT}/scenario.json") else {}
INTRO = json.load(open(f"{OUT}/offsets.json"))["intro"] if os.path.exists(f"{OUT}/offsets.json") else (sc.get("titleSeconds", 2.5) if sc.get("title") else 0)
T0 = timing["trimStart"]
steps = [(s["i"], s["start"] - T0 + INTRO, s["end"] - T0 + INTRO, s.get("say", "")) for s in timing["steps"]]

# frames: 1 s into each step (or the middle of short steps)
paths = []
for i, a, b, say in steps:
    t = min(a + 1.0, (a + b) / 2)
    p = f"{OUT}/review_{i:02d}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", VIDEO, "-frames:v", "1", "-vf", "scale=640:-1", p], check=True)
    paths.append(p)

try:
    from PIL import Image, ImageDraw, ImageFont
    ims = [Image.open(p) for p in paths]
    w, h = ims[0].size
    cols = 2 if len(ims) > 1 else 1
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 16) + 16, rows * (h + 44) + 16), "#111")
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(os.path.expanduser("~/.cache/demo-video/fonts/Inter-Medium.ttf"), 15)
    except Exception:
        font = ImageFont.load_default()
    for k, (im, (i, a, b, say)) in enumerate(zip(ims, steps)):
        x, y = 16 + (k % cols) * (w + 16), 16 + (k // cols) * (h + 44)
        sheet.paste(im, (x, y))
        d.text((x, y + h + 6), f"step {i}  {a:.1f}s -> {b:.1f}s   {say[:70]}", fill="white", font=font)
    sheet.save(f"{OUT}/review.png")
    for p in paths:
        os.remove(p)
    print(f"contact sheet: {OUT}/review.png")
except ImportError:
    print("PIL missing; per-step frames left as " + ", ".join(paths))

# voice onsets vs step starts
# use the bare voice track when it exists (music would hide the pauses), shifted by the intro card
vsrc = f"{OUT}/voice.wav" if os.path.exists(f"{OUT}/voice.wav") else VIDEO
r = subprocess.run(["ffmpeg", "-i", vsrc, "-af", "silencedetect=n=-40dB:d=0.25", "-f", "null", "-"], capture_output=True, text=True)
onsets = [float(x) + (INTRO if vsrc != VIDEO else 0) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", VIDEO],
                           capture_output=True, text=True).stdout.strip())
print(f"video: {dur:.1f}s, {len(steps)} steps, {len(onsets)} voice onsets")
worst = 0
for i, a, b, say in steps:
    if not say:
        print(f"step {i}: silent, {b - a:.1f}s")
        continue
    near = [o for o in onsets if a - 0.15 <= o <= a + 1.5]
    if near:
        gap = near[0] - a
        worst = max(worst, abs(gap))
        print(f"step {i}: voice starts {gap:+.2f}s after step start   ({say[:50]})")
    else:
        print(f"step {i}: NO voice onset found near {a:.1f}s   ({say[:50]})")
if worst > 0.3:
    print(f"WARNING: worst sync gap {worst:.2f}s")
long_gaps = [(i, b - a) for i, a, b, say in steps if b - a > 8]
for i, g in long_gaps:
    print(f"note: step {i} lasts {g:.1f}s — consider splitting it or shortening its actions")
