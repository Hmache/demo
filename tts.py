#!/usr/bin/env python3
"""Generate one narration clip per step and record each clip's duration.

Usage: python3 tts.py scenario.json OUT_DIR
       python3 tts.py --preview "One line to hear" OUT_DIR [lang]   -> OUT_DIR/voices-preview.mp3 (several voices)
Writes OUT_DIR/audio/step_XX.wav and OUT_DIR/durations.json ({"0": 2.41, ...}).
Engines (scenario.voice.engine): kokoro (default, local, free) | openai | elevenlabs | none

Voice quality steps (all engines): the narration text is normalised for speech (URLs, %, $, units, arrows,
custom pronunciations), then every clip is loudness-normalised, lightly EQ'd and compressed so the
narration sounds even and "produced". Set voice.polish = false to skip the audio chain.
Kokoro extras: voice blends ("af_heart+af_bella" or "af_heart*0.7+af_sky*0.3"), sentence/clause pauses.
"""
import json, os, re, subprocess, sys, urllib.request

MODELS = os.environ.get("KOKORO_DIR", os.path.expanduser("~/.cache/demo-video/models"))

# Kokoro voices worth recommending, by language (lang code for Kokoro -> voices)
KOKORO_LANGS = {
    "en-us": ["af_heart", "af_bella", "af_nova", "af_sky", "am_michael", "am_fenrir", "am_puck", "am_onyx"],
    "en-gb": ["bf_emma", "bf_isabella", "bf_lily", "bm_george", "bm_daniel", "bm_lewis"],
    "fr-fr": ["ff_siwis"], "es": ["ef_dora", "em_alex"], "it": ["if_sara", "im_nicola"],
    "pt-br": ["pf_dora", "pm_alex"], "ja": ["jf_alpha", "jm_kumo"], "cmn": ["zf_xiaoxiao", "zm_yunxi"], "hi": ["hf_alpha", "hm_omega"],
}
PREFIX_LANG = {"a": "en-us", "b": "en-gb", "f": "fr-fr", "e": "es", "i": "it", "p": "pt-br", "j": "ja", "z": "cmn", "h": "hi"}


# ---------- text normalisation: what the voice should actually say ----------
UNITS = {"s": "seconds", "sec": "seconds", "ms": "milliseconds", "min": "minutes", "h": "hours", "px": "pixels",
         "kb": "kilobytes", "mb": "megabytes", "gb": "gigabytes", "tb": "terabytes", "kg": "kilos", "km": "kilometres", "x": "times", "fps": "frames per second"}
CURRENCY = {"$": "dollars", "€": "euros", "£": "pounds", "¥": "yen"}
SYMBOLS = [("→", ", then "), ("->", ", then "), ("&", " and "), (" + ", " plus "), ("%", " percent"), ("≈", " about "), ("~", " about "),
           ("e.g.", "for example"), ("i.e.", "that is"), ("etc.", "et cetera"), ("vs.", "versus"), (" vs ", " versus "),
           ("⌘+", "command "), ("⌘", "command"), ("⇧", "shift"), ("⌥", "option"), ("Ctrl+", "control "), ("Cmd+", "command ")]


def normalise(text, pronounce=None, lang="en-us"):
    t = text.strip()
    for k, v in (pronounce or {}).items():                       # user-supplied pronunciations first (brand names)
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
    for a, b in SYMBOLS:
        t = t.replace(a, b)
    t = re.sub(r"https?://", "", t)
    t = re.sub(r"\b([a-z0-9-]+)\.(com|io|ai|net|org|app|dev|fr|co|eu)\b(/\S*)?", lambda m: f"{m.group(1)} dot {m.group(2)}" + (" slash " + m.group(3)[1:].replace("/", " slash ") if m.group(3) else ""), t)
    t = re.sub(r"([$€£¥])\s?(\d[\d,.]*)\s?([kKmM])?\b", lambda m: f"{m.group(2)}{' thousand' if (m.group(3) or '').lower() == 'k' else ' million' if m.group(3) else ''} {CURRENCY[m.group(1)]}", t)
    t = re.sub(r"\b(\d+(?:\.\d+)?)\s?(ms|s|sec|min|h|px|kb|mb|gb|tb|kg|km|x|fps)\b", lambda m: f"{m.group(1)} {UNITS[m.group(2).lower()]}", t, flags=re.I)
    t = re.sub(r"\bv(\d+(?:\.\d+)*)\b", r"version \1", t)
    t = re.sub(r"(\d)\.(\d)", r"\1 point \2", t)                   # 2.5 -> 2 point 5
    t = re.sub(r"(\d|dollars|euros|pounds|yen)\s*/\s*(month|year|week|day|user|seat|hour|mo|yr)\b",
               lambda m: m.group(1) + " per " + {"mo": "month", "yr": "year"}.get(m.group(2), m.group(2)), t)
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r"\b(\d{1,3}),(\d{3})\b", r"\1\2", t)                # 1,200 -> 1200
    t = re.sub(r"\s+", " ", t).strip()
    return t


def voice_lang(v):
    return v.get("lang") or PREFIX_LANG.get(str(v.get("voice", "af_heart"))[:1], "en-us")


# ---------- audio helpers ----------
def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def polish(src, dst, enabled=True, room=0.18):
    """Broadcast-style chain: trim silence, high-pass, presence lift, gentle compression, loudness -16 LUFS, tail padding."""
    chain = [f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence={room},areverse"]
    if enabled:
        chain += ["highpass=f=80", "equalizer=f=220:t=q:w=1.2:g=-1.5", "equalizer=f=3000:t=q:w=1:g=2", "equalizer=f=9000:t=q:w=1.5:g=1",
                  "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=140:makeup=2", "deesser=i=0.3",
                  "loudnorm=I=-16:TP=-1.5:LRA=9"]
    chain += ["adelay=80|80", "apad=pad_dur=0.05"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", ",".join(chain), "-ar", "44100", "-ac", "2", dst], check=True)


def http(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


# ---------- engines ----------
_kokoro = None


def kokoro_voice(k, spec):
    """'af_heart' | 'af_heart+af_bella' | 'af_heart*0.7+af_sky*0.3' -> style array."""
    import numpy as np
    parts = [p.strip() for p in str(spec).split("+") if p.strip()]
    if len(parts) == 1 and "*" not in parts[0]:
        return parts[0]
    total, mix = 0.0, None
    for p in parts:
        name, _, w = p.partition("*")
        w = float(w) if w else 1.0
        st = k.get_voice_style(name.strip()) * w
        mix = st if mix is None else mix + st
        total += w
    return (mix / total).astype("float32")


def synth(text, v, tmp):
    """Return path of a raw clip (wav/mp3) for this text with the configured engine."""
    global _kokoro
    engine = v.get("engine", "kokoro")
    if engine == "kokoro":
        if _kokoro is None:
            from kokoro_onnx import Kokoro
            _kokoro = Kokoro(f"{MODELS}/kokoro-v1.0.onnx", f"{MODELS}/voices-v1.0.bin")
        import soundfile as sf
        samples, sr = _kokoro.create(text, voice=kokoro_voice(_kokoro, v.get("voice", "af_heart")), speed=float(v.get("speed", 1.0)),
                                     lang=voice_lang(v), sentence_pause=float(v.get("sentencePause", 0.35)), clause_pause=float(v.get("clausePause", 0.12)))
        sf.write(tmp + ".wav", samples, sr)
        return tmp + ".wav"
    if engine == "openai":
        audio = http("https://api.openai.com/v1/audio/speech",
                     {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"},
                     {"model": v.get("model", "gpt-4o-mini-tts"), "voice": v.get("voice", "alloy"), "input": text, "response_format": "mp3",
                      "speed": float(v.get("speed", 1.0)),
                      **({"instructions": v["instructions"]} if v.get("instructions") else {})})
        open(tmp + ".mp3", "wb").write(audio)
        return tmp + ".mp3"
    if engine == "elevenlabs":
        vid = v.get("voice", "21m00Tcm4TlvDq8ikWAM")
        audio = http(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                     {"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
                     {"text": text, "model_id": v.get("model", "eleven_multilingual_v2"),
                      "voice_settings": {"stability": float(v.get("stability", 0.5)), "similarity_boost": float(v.get("similarity", 0.8)),
                                         "style": float(v.get("style", 0.2)), "use_speaker_boost": True}})
        open(tmp + ".mp3", "wb").write(audio)
        return tmp + ".mp3"
    sys.exit(f"unknown engine {engine}")


# ---------- main ----------
if __name__ == "__main__":
    if sys.argv[1] == "--preview":
        line, out = sys.argv[2], sys.argv[3]
        lang = sys.argv[4] if len(sys.argv) > 4 else "en-us"
        os.makedirs(f"{out}/audio", exist_ok=True)
        parts = []
        for name in KOKORO_LANGS.get(lang, KOKORO_LANGS["en-us"]):
            v = {"engine": "kokoro", "voice": name, "lang": lang}
            raw = synth(f"{name.split('_')[1].capitalize()}. {normalise(line)}", v, f"{out}/audio/prev_{name}")
            polish(raw, f"{out}/audio/prev_{name}.wav" if not raw.endswith(".wav") else f"{out}/audio/prevp_{name}.wav")
            parts.append(f"{out}/audio/prevp_{name}.wav")
            print(f"{name}: {duration(parts[-1]):.1f}s")
        with open(f"{out}/preview.txt", "w") as fh:
            fh.write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{out}/preview.txt", "-c:a", "libmp3lame", "-q:a", "3", f"{out}/voices-preview.mp3"], check=True)
        print(f"preview: {out}/voices-preview.mp3  (each clip starts with the voice's name)")
        sys.exit(0)

    scenario = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(f"{out}/audio", exist_ok=True)
    v = scenario.get("voice", {}) or {}
    engine = v.get("engine", "kokoro")
    pron = scenario.get("pronounce") or {}
    durations = {}
    for i, step in enumerate(scenario["steps"]):
        text = (step.get("say") or "").strip()
        if not text or engine == "none":
            continue
        spoken = normalise(text, pron, voice_lang(v))
        dst = f"{out}/audio/step_{i:02d}.wav"
        raw = synth(spoken, v, f"{out}/audio/raw_{i:02d}")
        polish(raw, dst, enabled=v.get("polish", True) is not False)
        os.remove(raw)
        durations[str(i)] = round(duration(dst), 3)
        print(f"step {i}: {durations[str(i)]}s  {spoken[:70]}")
    json.dump(durations, open(f"{out}/durations.json", "w"), indent=1)
