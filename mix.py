#!/usr/bin/env python3
"""Assemble frames + narration + captions (+ optional music) into the final MP4.

Usage: python3 mix.py scenario.json OUT_DIR [output.mp4]
Needs OUT_DIR/frames.json, OUT_DIR/timing.json (record.js), OUT_DIR/durations.json + audio/ (tts.py).
Also writes OUT_DIR/captions.srt (for YouTube/LinkedIn uploads).
"""
import json, os, subprocess, sys

sc = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
DST = sys.argv[3] if len(sys.argv) > 3 else os.path.join(OUT, "demo.mp4")
frames = json.load(open(f"{OUT}/frames.json"))
timing = json.load(open(f"{OUT}/timing.json"))
dpath = f"{OUT}/durations.json"
durs = json.load(open(dpath)) if os.path.exists(dpath) else {}
VPT = sc.get("viewport") or {}
W, H = VPT.get("width", 1920), VPT.get("height", 1080)
T0, END = timing["trimStart"], timing["end"]
TOTAL = END - T0
FPS = sc.get("fps", 30)

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


cues = []
for st in timing["steps"]:
    if not st.get("say"):
        continue
    a = st["start"] - T0
    b = a + durs[str(st["i"])] + 0.3 if str(st["i"]) in durs else st["end"] - T0
    cues.append((a, min(b, st["end"] - T0), st["say"].replace("\n", " ")))
with open(f"{OUT}/captions.srt", "w") as fh:
    for n, (a, b, t) in enumerate(cues, 1):
        fh.write(f"{n}\n{ts(a)} --> {ts(b)}\n{t}\n\n")

cap = sc.get("captions", True)
font = sc.get("captionFont", "Inter")
fs = round(H * 0.034)
ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{fs},&H00FFFFFF,&H00FFFFFF,&H26101010,&H26101010,0,0,0,0,100,100,0,0,3,{round(fs*0.45)},0,2,{round(W*0.12)},{round(W*0.12)},{round(H*0.06)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "".join(f"Dialogue: 0,{ts(a, 1)},{ts(b, 1)},Cap,,0,0,0,,{t.replace('{', '(').replace('}', ')')}\n" for a, b, t in cues)
open(f"{OUT}/captions.ass", "w").write(ass)

# 3. ffmpeg graph: video (+captions), narration clips placed at their step start, optional ducked music.
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{OUT}/frames.txt"]
vf = f"fps={FPS},scale={W}:{H}:flags=lanczos,format=yuv420p"
if cap and cues:
    fdir = os.path.expanduser("~/.cache/demo-video/fonts")
    vf += f",ass={OUT}/captions.ass" + (f":fontsdir={fdir}" if os.path.isdir(fdir) else "")
filters = [f"[0:v]{vf}[v]"]
labels, idx = [], 1
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
if sc.get("gif"):
    g = os.path.splitext(DST)[0] + ".gif"
    gw = min(W, 960)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", DST, "-vf",
                    f"fps=12,scale={gw}:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    g], check=True)
print(f"OK {DST}  {TOTAL:.1f}s  {W}x{H}  voice clips: {len(labels)}  captions: {len(cues) if cap else 0}")
