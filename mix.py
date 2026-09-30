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
XF = 0.5 if sc.get("transitions") else 0.0          # crossfade length between cards and the recording
CARD_S = sc.get("cardSeconds", 2.2)                 # full-screen section cards ("## Title" in the scenario)
BGR = BRAND[4:6] + BRAND[2:4] + BRAND[0:2]          # ASS wants BBGGRR

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


INTRO = (sc.get("titleSeconds", 2.5) - XF) if sc.get("title") else 0   # sidecar SRT must account for the title card
json.dump({"intro": INTRO}, open(f"{OUT}/offsets.json", "w"))
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
Style: Label,{font},{round(H*0.027)},&H00FFFFFF,&H00FFFFFF,&H00{BGR},&H00{BGR},1,0,0,0,100,100,0,0,3,{round(H*0.011)},0,7,{FX + round(H*0.03)},0,{FY + round(H*0.03)},1
Style: Card,{font},{round(H*0.062)},&H00FFFFFF,&H00FFFFFF,&H000F172A,&H000F172A,1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: CardSub,{font},{round(H*0.03)},&H00{BGR},&H00FFFFFF,&H000F172A,&H000F172A,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "".join(f"Dialogue: 0,{ts(a, 1)},{ts(b, 1)},Cap,,0,0,0,,{t.replace('{', '(').replace('}', ')')}\n" for a, b, t in cues)
if sc.get("progressBar"):  # thin brand-colored bar growing along the bottom edge (ASS drawing, scaled over time)
    bh = max(3, round(H * 0.005))
    ass += (f"Dialogue: 1,0:00:00.00,{ts(TOTAL, 1)},Cap,,0,0,0,,{{\\an7\\pos(0,{H - bh})\\bord0\\shad0\\1c&H{BGR}&"
            f"\\fscx0\\fscy100\\t(0,{int(TOTAL * 1000)},\\fscx100)\\p1}}m 0 0 l {W} 0 {W} {bh} 0 {bh}{{\\p0}}\n")
# Lower-third labels ("# Title" in a step) and full-screen section cards ("## Title").
n_label = 0
for st in timing["steps"]:
    a = st["start"] - T0
    if st.get("label") and sc.get("chapters", True):
        n_label += 1
        b = min(a + 3.2, st["end"] - T0)
        ass += f"Dialogue: 2,{ts(a, 1)},{ts(b, 1)},Label,,0,0,0,,{{\\fad(200,350)}}{n_label:02d}\\h\\h{st['label'].replace('{', '(').replace('}', ')')}\n"
    if st.get("card"):
        b = a + CARD_S
        ass += (f"Dialogue: 3,{ts(a, 1)},{ts(b, 1)},Card,,0,0,0,,{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H2A170F&\\fad(300,450)\\p1}}"
                f"m 0 0 l {W} 0 {W} {H} 0 {H}{{\\p0}}\n")
        ass += (f"Dialogue: 4,{ts(a, 1)},{ts(b, 1)},Card,,0,0,0,,{{\\an5\\pos({W // 2},{round(H * 0.47)})\\fad(300,450)}}"
                f"{st['card'].replace('{', '(').replace('}', ')')}\n")
        ass += (f"Dialogue: 4,{ts(a, 1)},{ts(b, 1)},CardSub,,0,0,0,,{{\\an5\\pos({W // 2},{round(H * 0.56)})\\bord0\\shad0\\1c&H{BGR}&\\fad(300,450)\\p1}}"
                f"m 0 0 l {round(W * 0.05)} 0 {round(W * 0.05)} {max(3, round(H * 0.006))} 0 {max(3, round(H * 0.006))}{{\\p0}}\n")
open(f"{OUT}/captions.ass", "w").write(ass)

post = ""
if (cap and cues) or sc.get("progressBar") or any(st.get("label") or st.get("card") for st in timing["steps"]):
    post += f",ass={OUT}/captions.ass" + (f":fontsdir={FONTS}" if os.path.isdir(FONTS) else "")

# 3. Voice track (all clips at their step start) -> voice.wav. Needed on its own for the presenter bubble.
voice_clips = []
for st in timing["steps"]:
    wav = f"{OUT}/audio/step_{st['i']:02d}.wav"
    if str(st["i"]) in durs and os.path.exists(wav):
        voice_clips.append((wav, int(round((st["start"] - T0) * 1000))))
HAS_VOICE = bool(voice_clips)
if HAS_VOICE:
    c = ["ffmpeg", "-y", "-loglevel", "error"]
    fl = []
    for k, (wav, ms) in enumerate(voice_clips):
        c += ["-i", wav]
        fl.append(f"[{k}:a]adelay={ms}|{ms},apad[a{k}]")
    fl.append("".join(f"[a{k}]" for k in range(len(voice_clips))) + f"amix=inputs={len(voice_clips)}:normalize=0:duration=longest,atrim=0:{TOTAL:.3f}[v]")
    subprocess.run(c + ["-filter_complex", ";".join(fl), "-map", "[v]", "-ar", "44100", "-ac", "2", f"{OUT}/voice.wav"], check=True)


# 3b. Music: a file, or "auto" = a soft generated ambient bed (no licensing worries).
def ambient(path, seconds, sr=44100):
    import numpy as np
    t_all = np.arange(int(seconds * sr)) / sr
    out = np.zeros_like(t_all)
    beat = 60 / 72.0
    chords = [(0, 4, 7, 11), (7, 11, 14, 17), (9, 12, 16, 19), (5, 9, 12, 16)]   # Cmaj7 G Am7 F, in semitones from C3
    base = 130.81
    bar = 4 * beat
    seg = 2 * bar
    n = 0
    while n * seg < seconds:
        ch = chords[n % len(chords)]
        a, b = int(n * seg * sr), min(int((n + 1) * seg * sr + 1.2 * sr), len(t_all))
        tt = t_all[a:b] - n * seg
        env = np.minimum(1, tt / 1.4) * np.minimum(1, np.maximum(0, (seg + 1.2 - tt) / 1.6))
        for semi in ch:
            f = base * 2 ** (semi / 12)
            vib = 1 + 0.004 * np.sin(2 * np.pi * 0.2 * tt + semi)
            out[a:b] += env * (0.5 * np.sin(2 * np.pi * f * vib * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * tt) + 0.12 * np.sin(2 * np.pi * 3 * f * tt)) / len(ch)
        out[a:b] += env * 0.35 * np.sin(2 * np.pi * base / 2 * 2 ** (ch[0] / 12) * tt)   # sub bass
        for k in range(8):                                                                 # soft arpeggio pluck each beat
            st_ = int(k * beat * sr)
            if a + st_ >= b:
                break
            f = base * 2 * 2 ** (ch[k % len(ch)] / 12)
            span = min(int(1.1 * sr), b - a - st_)
            tp = np.arange(span) / sr
            out[a + st_:a + st_ + span] += 0.12 * np.exp(-tp * 3.2) * np.sin(2 * np.pi * f * tp) * env[st_:st_ + span]
        n += 1
    out = out / (np.max(np.abs(out)) + 1e-9) * 0.5
    import soundfile as sf
    sf.write(path, out.astype("float32"), sr)


music = sc.get("music")
if music == "auto":
    music = f"{OUT}/music_auto.wav"
    ambient(music, TOTAL + 6)
if music and not os.path.exists(music):
    sys.exit(f"music file not found: {music}")


# 3c. Small overlays: logo watermark, presenter bubble (photo + live voice bars).
def circle_photo(src, size):
    from PIL import Image, ImageDraw, ImageOps
    im = Image.open(src).convert("RGBA")
    im = ImageOps.fit(im, (size, size), centering=(0.5, 0.4))
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
    im.putalpha(m)
    return im


# Opt-in only (`presenter: bubble` in the scenario): the pill covers part of the page, so no template turns it on.
PRESENTER = sc.get("presenter") if HAS_VOICE and sc.get("presenter") not in (None, False, "", "no", "none", "off") else None
pill = None
if PRESENTER:
    from PIL import Image, ImageDraw
    ph = round(H * 0.075)
    photo = sc.get("presenterImage")
    pw = round(ph * (3.4 if photo else 2.4))
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], ph // 2, fill=(15, 23, 42, 255))
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], ph // 2, outline=(255, 255, 255, 60), width=1)
    bars_x = round(ph * 0.35)
    if photo and os.path.exists(photo):
        pic = circle_photo(photo, ph - round(ph * 0.16))
        pill.paste(pic, (round(ph * 0.08), round(ph * 0.08)), pic)
        bars_x = ph
    pill.save(f"{OUT}/pill.png")
    BARS_W, BARS_H = pw - bars_x - round(ph * 0.35), round(ph * 0.5)
    BARS_Y = (ph - BARS_H) // 2
    NB = 12                                            # number of bars: a cover with gaps turns the spectrum into discrete bars
    comb = Image.new("RGBA", (BARS_W, BARS_H), (15, 23, 42, 255))
    cd = ImageDraw.Draw(comb)
    bw = BARS_W / NB
    for k in range(NB):
        cd.rounded_rectangle([round(k * bw + bw * 0.22), 0, round((k + 1) * bw - bw * 0.22), BARS_H - 1], max(1, round(bw * 0.28)), fill=(0, 0, 0, 0))
    comb.save(f"{OUT}/comb.png")
    PX, PY = (FX + round(H * 0.03) if FRAME else round(H * 0.03)), (H - ph - round(H * 0.03)) if not FRAME else (FY + VH - ph - round(H * 0.03))
LOGO = sc.get("logo")
if LOGO and not os.path.exists(LOGO):
    print(f"note: logo not found, skipping: {LOGO}")
    LOGO = None
if LOGO:
    from PIL import Image
    im = Image.open(LOGO).convert("RGBA")
    lh = round(H * 0.055)
    im = im.resize((max(1, round(im.width * lh / im.height)), lh))
    im.save(f"{OUT}/logo.png")
    LX, LY = (W - im.width - round(H * 0.03)), (round(H * 0.03) if not FRAME else (FY + VH + (H - FY - VH - lh) // 2))
    if FRAME and (H - FY - VH) < lh + 8:
        LY = round(H * 0.03)

# 4. Main render: frames (+frame) + overlays + ASS, voice + ducked music.
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{OUT}/frames.txt"]
idx = 1
inputs = {}
def add_input(*args):
    global idx
    cmd.extend(args)
    idx += 1
    return idx - 1
if FRAME:
    inputs["bg"] = add_input("-i", f"{OUT}/frame_bg.png")
    inputs["mask"] = add_input("-i", f"{OUT}/frame_mask.png")
if HAS_VOICE:
    inputs["voice"] = add_input("-i", f"{OUT}/voice.wav")
if pill is not None:
    inputs["pill"] = add_input("-i", f"{OUT}/pill.png")
    inputs["comb"] = add_input("-i", f"{OUT}/comb.png")
if LOGO:
    inputs["logo"] = add_input("-i", f"{OUT}/logo.png")
if music:
    inputs["music"] = add_input("-stream_loop", "-1", "-i", music)

filters = []
if FRAME:
    filters += [f"[0:v]fps={FPS},scale={VW}:{VH}:flags=lanczos,format=rgba[v0]", f"[v0][{inputs['mask']}:v]alphamerge[v1]",
                f"[{inputs['bg']}:v][v1]overlay={FX}:{FY}:format=auto[vc]"]
else:
    filters += [f"[0:v]fps={FPS},scale={W}:{H}:flags=lanczos[vc]"]
cur = "[vc]"
if pill is not None:
    filters += [f"[{inputs['voice']}:a]showfreqs=s={NB}x{BARS_H}:mode=bar:ascale=cbrt:fscale=log:win_size=32:colors=white|white,"   # no 'rate=' (ffmpeg 4.x)
                f"fps={FPS},scale={BARS_W}:{BARS_H}:flags=neighbor,format=rgba,colorkey=black:0.3:0.1[bars]",
                f"[{inputs['pill']}:v][bars]overlay={bars_x}:{BARS_Y}:format=auto[pillb]",
                f"[pillb][{inputs['comb']}:v]overlay={bars_x}:{BARS_Y}:format=auto[pillv]",
                f"{cur}[pillv]overlay={PX}:{PY}:format=auto[vp]"]
    cur = "[vp]"
if LOGO:
    filters += [f"{cur}[{inputs['logo']}:v]overlay={LX}:{LY}:format=auto[vl]"]
    cur = "[vl]"
filters += [f"{cur}format=yuv420p{post}[v]"]
amap = None
if HAS_VOICE:
    AF = "aformat=sample_fmts=fltp:channel_layouts=stereo:sample_rates=44100"        # explicit formats keep ffmpeg 4.x happy
    filters.append(f"[{inputs['voice']}:a]{AF},asplit[vo][sc]" if music else f"[{inputs['voice']}:a]{AF}[vo]")
    amap = "[vo]"
if music:
    mv = sc.get("musicVolume", 0.25)
    fade = max(TOTAL - 2, 0)
    filters.append(f"[{inputs['music']}:a]aformat=sample_fmts=fltp:channel_layouts=stereo:sample_rates=44100,volume={mv},atrim=0:{TOTAL:.3f},afade=t=in:d=1,afade=t=out:st={fade:.2f}:d=2[m]")
    if HAS_VOICE:  # duck music under the voice
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


# 5. Optional title / outro cards around the finished video (second pass keeps voice sync intact), crossfaded.
def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def card(dst, lines, secs, qr=None):
    """lines = [(text, size_ratio, color)] drawn centered, stacked; optional QR code below; fades in and out."""
    fnt = f"fontfile={FONT_FILE}:" if FONT_FILE else "font=sans:"
    n = len(lines)
    shift = -round(H * 0.16) if qr else 0
    draws = []
    for k, line in enumerate(lines):
        text, ratio, color = line[:3]
        x = line[3] if len(line) > 3 else "(w-text_w)/2"          # optional fixed x: a left-aligned list
        fsz = round(H * ratio)
        y = f"(h-text_h)/2+{round(H * 0.075 * (k - (n - 1) / 2)) + shift:+d}"
        draws.append(f"drawtext={fnt}text='{esc(text)}':fontsize={fsz}:fontcolor={color}:x={x}:y={y}")
    c = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x0f172a:s={W}x{H}:r={FPS}:d={secs}",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    fc = "[0:v]" + ",".join(draws) + "[t]"
    if qr:
        c += ["-i", qr]
        fc += f";[t][2:v]overlay=(W-w)/2:{round(H * 0.5)}[t2]"
        last = "[t2]"
    else:
        last = "[t]"
    fc += f";{last}fade=t=in:d=0.5,fade=t=out:st={secs - 0.5:.2f}:d=0.5,format=yuv420p[v]"
    subprocess.run(c + ["-t", str(secs), "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", dst], check=True)


def dur(x):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", x], capture_output=True, text=True).stdout.strip() or 0)


parts = []
if sc.get("title"):
    lines = [(sc["title"], 0.07, "white")]
    if sc.get("subtitle"):
        lines.append((sc["subtitle"], 0.032, f"0x{BRAND}"))
    card(f"{OUT}/card_intro.mp4", lines, sc.get("titleSeconds", 2.5))
    parts.append(f"{OUT}/card_intro.mp4")
if parts or sc.get("outro"):
    if amap is None:  # give the main part a silent track so concat works
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", DST, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-c:v", "copy", "-c:a", "aac", "-shortest", f"{OUT}/main_a.mp4"], check=True)
        DST_MAIN = f"{OUT}/main_a.mp4"
    else:
        shutil.move(DST, f"{OUT}/main.mp4")
        DST_MAIN = f"{OUT}/main.mp4"
    parts.append(DST_MAIN)
    # Recap card: the chapter labels as a short list before the call-to-action ("recap: yes|no|auto", auto = 3+ chapters).
    labels = [st["label"] for st in timing["steps"] if st.get("label")] if sc.get("chapters", True) else []
    recap = sc.get("recap", "auto")
    if (recap is True or (recap == "auto" and len(labels) >= 3 and sc.get("outro"))) and labels:
        items = [f"{k + 1:02d}   {l}" for k, l in enumerate(labels[:6])]
        left = round(W / 2 - 0.5 * 0.55 * round(H * 0.042) * max(len(i) for i in items))     # common left edge (Inter ~0.55 em/char)
        lines = [(sc.get("recapTitle", "In this demo"), 0.03, f"0x{BRAND}", left)] + [(i, 0.042, "white", left) for i in items]
        card(f"{OUT}/card_recap.mp4", lines, sc.get("recapSeconds", 1.6 + 0.7 * min(len(labels), 6)))
        parts.append(f"{OUT}/card_recap.mp4")
    if sc.get("outro"):
        qr = None
        if sc.get("qr"):
            try:
                import qrcode
                img = qrcode.make(sc["qr"], box_size=10, border=1).convert("RGB")
                side = round(H * 0.26)
                img = img.resize((side, side))
                img.save(f"{OUT}/qr.png")
                qr = f"{OUT}/qr.png"
            except ImportError:
                print("note: pip install qrcode to get a QR code on the outro card")
        card(f"{OUT}/card_outro.mp4", [(sc["outro"], 0.045, "white")], sc.get("outroSeconds", 4 if qr else 3), qr)
        parts.append(f"{OUT}/card_outro.mp4")
    c = ["ffmpeg", "-y", "-loglevel", "error"]
    for pth in parts:
        c += ["-i", pth]
    if XF and len(parts) > 1:
        ds = [dur(p) for p in parts]
        fc = [f"[{k}:v]settb=AVTB,fps={FPS}[p{k}]" for k in range(len(parts))]   # xfade needs identical timebases
        va, aa, off = "[p0]", "[0:a]", 0.0
        for k in range(1, len(parts)):
            off += ds[k - 1] - XF
            fc.append(f"{va}[p{k}]xfade=transition=fade:duration={XF}:offset={off:.3f}[v{k}]")
            fc.append(f"{aa}[{k}:a]acrossfade=d={XF}[a{k}]")
            va, aa = f"[v{k}]", f"[a{k}]"
        fc = ";".join(fc)
        vout, aout = va, aa
    else:
        fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
        vout, aout = "[v]", "[a]"
    subprocess.run(c + ["-filter_complex", fc, "-map", vout, "-map", aout, "-c:v", "libx264", "-preset", "medium",
                        "-crf", str(sc.get("crf", 18)), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", DST], check=True)
    TOTAL = dur(DST)

if sc.get("gif"):
    g = os.path.splitext(DST)[0] + ".gif"
    gw = min(W, 960)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", DST, "-vf",
                    f"fps=12,scale={gw}:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    g], check=True)
print(f"OK {DST}  {TOTAL:.1f}s  {W}x{H}  voice clips: {len(voice_clips)}  captions: {len(cues) if cap else 0}")
