#!/usr/bin/env python3
"""Generate one narration clip per step and record each clip's duration.

Usage: python3 tts.py scenario.json OUT_DIR
Writes OUT_DIR/audio/step_XX.wav and OUT_DIR/durations.json ({"0": 2.41, ...}).
Engines (scenario.voice.engine): kokoro (default, local, free) | openai | elevenlabs | none
"""
import json, os, subprocess, sys, urllib.request

scenario = json.load(open(sys.argv[1]))
out = sys.argv[2]
os.makedirs(f"{out}/audio", exist_ok=True)
v = scenario.get("voice", {}) or {}
engine = v.get("engine", "kokoro")
MODELS = os.environ.get("KOKORO_DIR", os.path.expanduser("~/.cache/demo-video/models"))


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def to_wav(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "44100", "-ac", "2", dst], check=True)


def http(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


kokoro = None
durations = {}
for i, step in enumerate(scenario["steps"]):
    text = (step.get("say") or "").strip()
    if not text or engine == "none":
        continue
    dst = f"{out}/audio/step_{i:02d}.wav"
    tmp = f"{out}/audio/raw_{i:02d}"
    if engine == "kokoro":
        if kokoro is None:
            from kokoro_onnx import Kokoro
            kokoro = Kokoro(f"{MODELS}/kokoro-v1.0.onnx", f"{MODELS}/voices-v1.0.bin")
        import soundfile as sf
        samples, sr = kokoro.create(text, voice=v.get("voice", "af_heart"),
                                    speed=float(v.get("speed", 1.0)), lang=v.get("lang", "en-us"))
        sf.write(tmp + ".wav", samples, sr)
        to_wav(tmp + ".wav", dst)
    elif engine == "openai":
        audio = http("https://api.openai.com/v1/audio/speech",
                     {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"},
                     {"model": v.get("model", "gpt-4o-mini-tts"), "voice": v.get("voice", "alloy"),
                      "input": text, "response_format": "mp3",
                      **({"instructions": v["instructions"]} if v.get("instructions") else {})})
        open(tmp + ".mp3", "wb").write(audio)
        to_wav(tmp + ".mp3", dst)
    elif engine == "elevenlabs":
        vid = v.get("voice", "21m00Tcm4TlvDq8ikWAM")
        audio = http(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                     {"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
                     {"text": text, "model_id": v.get("model", "eleven_multilingual_v2")})
        open(tmp + ".mp3", "wb").write(audio)
        to_wav(tmp + ".mp3", dst)
    else:
        sys.exit(f"unknown engine {engine}")
    for ext in (".wav", ".mp3"):
        if os.path.exists(tmp + ext):
            os.remove(tmp + ext)
    durations[str(i)] = round(duration(dst), 3)
    print(f"step {i}: {durations[str(i)]}s  {text[:60]}")

json.dump(durations, open(f"{out}/durations.json", "w"), indent=1)
