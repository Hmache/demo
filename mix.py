#!/usr/bin/env python3
"""Assemble frames + narration + captions (+ optional music) into the final MP4.

Usage: python3 mix.py scenario.json OUT_DIR [output.mp4]
Needs OUT_DIR/frames.json, OUT_DIR/timing.json (record.js), OUT_DIR/durations.json + audio/ (tts.py).
Also writes OUT_DIR/captions.srt (for YouTube/LinkedIn uploads).
"""
import json, os, shutil, subprocess, sys

sc = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
DST = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "demo.mp4")
frames = json.load(open(f"{OUT}/frames.json"))
timing = json.load(open(f"{OUT}/timing.json"))
dpath = f"{OUT}/durations.json"
durs = json.load(open(dpath)) if os.path.exists(dpath) else {}
VPT = sc.get("viewport") or {}
SCALE = sc.get("scale", 1)
W, H = VPT.get("width", 1920) * SCALE, VPT.get("height", 1080) * SCALE
BRAND = sc.get("brandColor", "#2563eb").lstrip("#")
FONTS = os.path.expanduser("~/.cache/demo-video/fonts")
FONT_FILE = f"{FONTS}/Inter-SemiBold.ttf" if os.path.exists(f"{FONTS}/Inter-SemiBold.ttf") else None
T0, END = timing["trimStart"], timing["end"]
TOTAL = END - T0
FPS = sc.get("fps", 30)

# 0. Optional "frame": the browser floats with rounded corners and a shadow on a brand-tinted gradient.
FRAME = bool(sc.get("frame"))
VW, VH = W, H                     # size of the recorded browser inside the canvas
FX = FY = 0
if FRAME:
    from PIL import Image, ImageDraw, ImageFilter
    landscape = W >= H
    k = 0.84 if landscape else 0.86
    VW, VH = round(W * k), round(H * k)
    VW -= VW % 2; VH -= VH % 2
    FX, FY = (W - VW) // 2, round((H - VH) * 0.3)       # above centre: captions live in the band below the video
    def hexrgb(h): return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    br = hexrgb(BRAND)
    top, bottom = (17, 24, 39), tuple(round(0.72 * c + 0.28 * b) for c, b in zip((30, 41, 59), br))
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    for y in range(H):
        t = y / max(H - 1, 1)
        col = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = col
    rad = round(min(VW, VH) * 0.022)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([FX, FY + round(H * 0.012), FX + VW, FY + VH + round(H * 0.012)], rad, fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(round(H * 0.02)))
    bg = Image.alpha_composite(bg.convert("RGBA"), sh).convert("RGB")
    bg.save(f"{OUT}/frame_bg.png")
    mask = Image.new("L", (VW, VH), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, VW - 1, VH - 1], rad, fill=255)
    mask.save(f"{OUT}/frame_mask.png")

# 1. Variable-rate frame list -> concat demuxer (each frame held until the next one).
kept = [f for f in frames if f["t"] >= T0]
before = [f for f in frames if f["t"] < T0]
if before:
    kept.insert(0, {"f": before[-1]["f"], "t": T0})
with open(f"{OUT}/frames.txt", "w") as fh:
    for a, b in zip(kept, kept[1:] + [{"t": END}]):
        fh.write(f"file 'frames/{a['f']}'\nduration {max(b['t'] - a['t'], 0.001):.4f}\n")
    fh.write(f"file 'frames/{kept[-1]['f']}'\n")


# 2. Captions (ASS for burn-in at native resolution, SRT as a sidecar file).
def ts(x, ass=False):
    x = max(x, 0)
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    return f"{h}:{m:02d}:{s:05.2f}" if ass else f"{h:02d}:{m:02d}:{int(s):02d},{int(round(s % 1 * 1000)) % 1000:03d}"


INTRO = sc.get("titleSeconds", 2.5) if sc.get("title") else 0   # sidecar SRT must account for the title card
cues = []
for st in timing["steps"]:
    if not st.get("say") or not sc.get("captions", True):
        continue
    a = st["start"] - T0
    b = a + durs[str(st["i"])] + 0.3 if str(st["i"]) in durs else st["end"] - T0
    cues.append((a, min(b, st["end"] - T0), st["say"].replace("\n", " ")))
with open(f"{OUT}/captions.srt", "w") as fh:
    for n, (a, b, t) in enumerate(cues, 1):
        fh.write(f"{n}\n{ts(a + INTRO)} --> {ts(b + INTRO)}\n{t}\n\n")

cap = sc.get("captions", True)
font = sc.get("captionFont", "Inter")
fs = round(H * 0.034)
MV = max(6, round((H - (FY + VH) - fs * 1.9) / 2)) if FRAME else round(H * 0.06)   # caption bottom margin
ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{fs},&H00FFFFFF,&H00FFFFFF,&H26101010,&H26101010,0,0,0,0,100,100,0,0,3,{round(fs*0.45)},0,2,{round(W*0.12)},{round(W*0.12)},{MV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "".join(f"Dialogue: 0,{ts(a, 1)},{ts(b, 1)},Cap,,0,0,0,,{t.replace('{', '(').replace('}', ')')}\n" for a, b, t in cues)
if sc.get("progressBar"):  # thin brand-colored bar growing along the bottom edge (ASS drawing, scaled over time)
    bh = max(3, round(H * 0.005))
    bgr = BRAND[4:6] + BRAND[2:4] + BRAND[0:2]
    ass += (f"Dialogue: 1,0:00:00.00,{ts(TOTAL, 1)},Cap,,0,0,0,,{{\\an7\\pos(0,{H - bh})\\bord0\\shad0\\1c&H{bgr}&"
            f"\\fscx0\\fscy100\\t(0,{int(TOTAL * 1000)},\\fscx100)\\p1}}m 0 0 l {W} 0 {W} {bh} 0 {bh}{{\\p0}}\n")
open(f"{OUT}/captions.ass", "w").write(ass)

# 3. ffmpeg graph: video (+captions), narration clips placed at their step start, optional ducked music.
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{OUT}/frames.txt"]
post = ""
if (cap and cues) or sc.get("progressBar"):
    post += f",ass={OUT}/captions.ass" + (f":fontsdir={FONTS}" if os.path.isdir(FONTS) else "")
if FRAME:
    cmd += ["-i", f"{OUT}/frame_bg.png", "-i", f"{OUT}/frame_mask.png"]
    filters = [f"[0:v]fps={FPS},scale={VW}:{VH}:flags=lanczos,format=rgba[v0]",
               f"[v0][2:v]alphamerge[v1]",
               f"[1:v][v1]overlay={FX}:{FY}:format=auto,format=yuv420p{post}[v]"]
    idx = 3
else:
    filters = [f"[0:v]fps={FPS},scale={W}:{H}:flags=lanczos,format=yuv420p{post}[v]"]
    idx = 1
labels = []
for st in timing["steps"]:
    wav = f"{OUT}/audio/step_{st['i']:02d}.wav"
    if str(st["i"]) in durs and os.path.exists(wav):
        cmd += ["-i", wav]
        ms = int(round((st["start"] - T0) * 1000))
        filters.append(f"[{idx}:a]adelay={ms}|{ms},apad[a{idx}]")
        labels.append(f"[a{idx}]")
        idx += 1
amap = None
if labels:
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,atrim=0:{TOTAL:.3f}[voice]")
    amap = "[voice]"
music = sc.get("music")
if music and not os.path.exists(music):
    sys.exit(f"music file not found: {music}")
if music:
    cmd += ["-stream_loop", "-1", "-i", music]
    mv = sc.get("musicVolume", 0.25)
    fade = max(TOTAL - 2, 0)
    filters.append(f"[{idx}:a]volume={mv},atrim=0:{TOTAL:.3f},afade=t=in:d=1,afade=t=out:st={fade:.2f}:d=2[m]")
    if amap:  # duck music under the voice
        filters.append("[voice]asplit[vo][sc]")
        filters.append("[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md]")
        filters.append("[vo][md]amix=inputs=2:normalize=0:duration=first[aout]")
        amap = "[aout]"
    else:
        amap = "[m]"
cmd += ["-filter_complex", ";".join(filters), "-map", "[v]"]
if amap:
    cmd += ["-map", amap, "-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(sc.get("crf", 18)), "-pix_fmt", "yuv420p",
        "-t", f"{TOTAL:.3f}", "-movflags", "+faststart", DST]
subprocess.run(cmd, check=True)


# 4. Optional title / outro cards, added around the finished video (second pass keeps voice sync intact).
def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def card(dst, lines, secs):
    """lines = [(text, size_ratio, color)] drawn centered, stacked; fades in and out."""
    fnt = f"fontfile={FONT_FILE}:" if FONT_FILE else "font=sans:"
    n = len(lines)
    draws = []
    for k, (text, ratio, color) in enumerate(lines):
        fs = round(H * ratio)
        y = f"(h-text_h)/2+{round(H * 0.075 * (k - (n - 1) / 2)):+d}"
        draws.append(f"drawtext={fnt}text='{esc(text)}':fontsize={fs}:fontcolor={color}:x=(w-text_w)/2:y={y}")
    vf = ",".join(draws + [f"fade=t=in:d=0.5,fade=t=out:st={secs - 0.5:.2f}:d=0.5", "format=yuv420p"])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x0f172a:s={W}x{H}:r={FPS}:d={secs}",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(secs), "-vf", vf,
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", dst], check=True)


parts = []
if sc.get("title"):
    lines = [(sc["title"], 0.07, "white")]
    if sc.get("subtitle"):
        lines.append((sc["subtitle"], 0.032, f"0x{BRAND}"))
    card(f"{OUT}/card_intro.mp4", lines, sc.get("titleSeconds", 2.5))
    parts.append(f"{OUT}/card_intro.mp4")
main_has_audio = amap is not None
if parts or sc.get("outro"):
    if not main_has_audio:  # give the main part a silent track so concat works
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", DST, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-c:v", "copy", "-c:a", "aac", "-shortest", f"{OUT}/main_a.mp4"], check=True)
        DST_MAIN = f"{OUT}/main_a.mp4"
    else:
        shutil.move(DST, f"{OUT}/main.mp4")
        DST_MAIN = f"{OUT}/main.mp4"
    parts.append(DST_MAIN)
    if sc.get("outro"):
        card(f"{OUT}/card_outro.mp4", [(sc["outro"], 0.045, "white")], sc.get("outroSeconds", 3))
        parts.append(f"{OUT}/card_outro.mp4")
    c = ["ffmpeg", "-y", "-loglevel", "error"]
    for pth in parts:
        c += ["-i", pth]
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
    subprocess.run(c + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
                        "-crf", str(sc.get("crf", 18)), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", DST], check=True)
    TOTAL = sum(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", x],
                                     capture_output=True, text=True).stdout.strip() or 0) for x in parts)

if sc.get("gif"):
    g = os.path.splitext(DST)[0] + ".gif"
    gw = min(W, 960)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", DST, "-vf",
                    f"fps=12,scale={gw}:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    g], check=True)
print(f"OK {DST}  {TOTAL:.1f}s  {W}x{H}  voice clips: {len(labels)}  captions: {len(cues) if cap else 0}")
