#!/usr/bin/env python3
"""Convert a plain-text scenario into the JSON the recorder uses.

Usage: python3 scenario.py scenario.txt > scenario.json

Format (see example-scenario.txt):

    url: https://app.example.com
    voice: af_heart            # optional settings, one per line, at the top
    size: 1920x1080

    Narration for step 1, in plain words.
    > click "Sign in"

    Narration for step 2.
    > type "Dupont" into "Search"
    > press Enter

Blank lines separate steps. Lines starting with ">" are actions, other lines are the narration.
Targets ("...") are the visible text, placeholder or label of an element (or a CSS selector).
"""
import json, os, re, sys

SETTINGS = {
    "url": "url", "voice": "voice", "engine": "engine", "lang": "lang", "language": "lang",
    "speed": "speed", "size": "size", "resolution": "size", "captions": "captions",
    "music": "music", "music volume": "musicVolume", "gif": "gif", "locale": "locale",
    "typing speed": "typeDelay", "pause": "gapAfterVoice", "login state": "storageState",
    "model": "model", "instructions": "instructions",
    "title": "title", "subtitle": "subtitle", "outro": "outro", "brand color": "brandColor", "color": "brandColor",
    "mobile": "mobile", "hd": "hd", "retina": "hd", "cookies": "cookies", "highlight clicks": "highlightClicks",
    "progress bar": "progressBar", "logo": "logo", "frame": "frame", "background": "frame", "show keys": "showKeys",
    "pronounce": "pronounce", "pronunciation": "pronounce", "polish": "polish", "voice polish": "polish",
    "sentence pause": "sentencePause", "clause pause": "clausePause", "stability": "stability", "style": "style", "similarity": "similarity",
    "template": "template", "qr": "qr", "presenter": "presenter", "presenter image": "presenterImage", "photo": "presenterImage",
    "transitions": "transitions", "font": "captionFont", "chapters": "chapters",
}
TEMPLATES = {   # bundles of settings; explicit settings written after `template:` override them
    "launch":      {"viewport": {"width": 1920, "height": 1080}, "frame": True, "progressBar": True, "highlightClicks": True, "transitions": True, "chapters": True},
    "walkthrough": {"viewport": {"width": 1920, "height": 1080}, "frame": False, "progressBar": True, "highlightClicks": True, "transitions": True, "chapters": True},
    "social":      {"viewport": {"width": 1080, "height": 1920}, "scale": 1, "frame": True, "progressBar": True, "highlightClicks": True, "transitions": True, "captions": True},
    "mobile":      {"viewport": {"width": 390, "height": 844}, "mobile": True, "scale": 2, "frame": True, "progressBar": True, "transitions": True},
    "minimal":     {"frame": False, "progressBar": False, "highlightClicks": False, "showKeys": False, "captions": True},
}
PRESETS = {"mobile": (390, 844), "phone": (390, 844), "tablet": (820, 1180), "desktop": (1920, 1080),
           "hd": (1280, 720), "1080p": (1920, 1080), "720p": (1280, 720), "square": (1080, 1080), "vertical": (1080, 1920)}
YES = {"yes", "on", "true", "1"}


def q(s):
    """Strip one pair of surrounding quotes."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'“”":
        return s[1:-1]
    if len(s) >= 2 and s[0] in "“«" and s[-1] in "”»":
        return s[1:-1].strip()
    return s


def target(s):
    """A target: "visible text", "visible text" #2, or a CSS selector."""
    s = s.strip()
    m = re.match(r"^(.*?)\s+#(\d+)$", s)
    if m and m.group(1)[:1] in "\"'\u201c":
        return f"{q(m.group(1))} #{m.group(2)}"
    return q(s)


def env(text):
    """Expand $NAME / ${NAME} from the environment, so secrets never sit in the scenario file."""
    def sub(m):
        name = m.group(1) or m.group(2)
        if name not in os.environ:
            raise ValueError(f"environment variable {name} is not set (pass it on the command line: {name}=... make.sh ...)")
        return os.environ[name]
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", sub, text)


def seconds_to_ms(s):
    m = re.match(r"^([\d.]+)\s*(ms|s|sec|secs|seconds?)?$", s.strip())
    if not m:
        raise ValueError(f"can't read duration '{s}'")
    v = float(m.group(1))
    return int(v if m.group(2) == "ms" else v * 1000)


QUOTED = r"(\"[^\"]*\"|'[^']*'|“[^”]*”)"


def action(line, n):
    s = line.strip()
    low = s.lower()
    m = re.match(rf"^(?:type|write|enter)\s+{QUOTED}(?:\s+(?:into|in|on)\s+(.+))?$", s, re.I)
    if m:
        a = {"type": "type", "text": env(q(m.group(1)))}
        if m.group(2):
            a["selector"] = target(m.group(2))
        return a
    m = re.match(rf"^fill\s+(.+?)\s+with\s+{QUOTED}$", s, re.I)
    if m:
        return {"type": "fill", "selector": target(m.group(1)), "text": env(q(m.group(2)))}
    m = re.match(rf"^(?:select|choose|pick)\s+{QUOTED}\s+(?:in|from)\s+(.+)$", s, re.I)
    if m:
        return {"type": "select", "value": q(m.group(1)), "selector": target(m.group(2))}
    m = re.match(r"^(?:go to|open|visit|navigate to)\s+(\S+)$", s, re.I)
    if m:
        return {"type": "goto", "url": q(m.group(1))}
    m = re.match(r"^(?:press|hit|key)\s+(.+)$", s, re.I)
    if m:
        return {"type": "press", "key": q(m.group(1))}
    m = re.match(r"^scroll\s+(down|up)(?:\s+(\d+))?", s, re.I)
    if m:
        px = int(m.group(2) or 600)
        return {"type": "scroll", "y": px if m.group(1).lower() == "down" else -px}
    m = re.match(r"^scroll\s+to\s+(.+)$", s, re.I)
    if m:
        return {"type": "scroll", "selector": target(m.group(1))}
    m = re.match(r"^wait\s+(?:for|until)\s+(.+?)(?:\s+(?:to appear|appears|is visible))?$", s, re.I)
    if m and not re.match(r"^[\d.]+\s*(ms|s|sec|secs|seconds?)?$", m.group(1).strip()):
        return {"type": "waitFor", "selector": target(m.group(1))}
    m = re.match(r"^(?:wait|pause)\s+(?:for\s+)?(.+)$", s, re.I)
    if m:
        return {"type": "wait", "ms": seconds_to_ms(m.group(1))}
    m = re.match(r"^(?:highlight|show|point out|circle)\s+(.+?)(?:\s+for\s+([\d.]+\s*(?:ms|s|sec|seconds?)))?$", s, re.I)
    if m:
        a = {"type": "highlight", "selector": target(m.group(1))}
        if m.group(2):
            a["ms"] = seconds_to_ms(m.group(2))
        return a
    m = re.match(r"^zoom\s+(?:out|back|reset)$", s, re.I)
    if m:
        return {"type": "zoom", "factor": 1}
    m = re.match(r"^zoom\s+(?:in\s+)?(?:into|on|to|onto)\s+(.+?)(?:\s+(?:x|by\s+)?([\d.]+)x?)?$", s, re.I)
    if m:
        a = {"type": "zoom", "selector": target(m.group(1))}
        if m.group(2):
            a["factor"] = float(m.group(2))
        return a
    m = re.match(rf"^(?:callout|say|label|note)\s+{QUOTED}\s+(?:at|on|near|above)\s+(.+?)(?:\s+for\s+([\d.]+\s*(?:ms|s|sec|seconds?)))?$", s, re.I)
    if m:
        a = {"type": "callout", "text": q(m.group(1)), "selector": target(m.group(2))}
        if m.group(3):
            a["ms"] = seconds_to_ms(m.group(3))
        return a
    m = re.match(r"^(?:dismiss|close|hide|reject)\s+(?:the\s+)?cookies?(?:\s+banner)?$", s, re.I)
    if m:
        return {"type": "dismissCookies"}
    m = re.match(r"^(?:hover over|hover on|hover|point at|move to)\s+(.+)$", s, re.I)
    if m:
        return {"type": "hover", "selector": target(m.group(1))}
    m = re.match(r"^(?:click on|click|tap on|tap|uncheck|check|open)\s+(.+)$", s, re.I)
    if m:
        return {"type": "click", "selector": target(m.group(1))}
    m = re.match(r"^(?:js|javascript|run)\s*:\s*(.+)$", s, re.I)
    if m:
        return {"type": "eval", "js": m.group(1)}
    raise ValueError(f"line {n}: don't understand the action '{s}'. "
                     "Use click / hover / type \"..\" into / fill .. with \"..\" / select \"..\" in / press / "
                     "scroll down|up|to / wait 2s / wait for / highlight / zoom into / zoom out / callout \"..\" at / dismiss cookies / go to / js:")


def parse(text):
    sc = {"steps": []}
    voice = {}
    lines = text.splitlines()
    i = 0
    # Settings header: "key: value" lines at the top (known keys only).
    while i < len(lines):
        raw = lines[i].strip()
        if not raw or raw.startswith("//"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z][A-Za-z ]*?)\s*:\s*(.+?)\s*(?:\s+#.*)?$", raw)
        key = m and SETTINGS.get(m.group(1).strip().lower())
        if not key:
            break
        val = m.group(2).strip()
        if key == "url":
            sc["url"] = val
        elif key == "template":
            if val.lower() not in TEMPLATES:
                raise ValueError(f"unknown template '{val}' (choose: {', '.join(TEMPLATES)})")
            sc.update(TEMPLATES[val.lower()])
            sc["template"] = val.lower()
        elif key == "music" and val.lower() in ("auto", "yes", "ambient", "generated"):
            sc["music"] = "auto"
        elif key in ("voice", "engine", "lang", "speed", "model", "instructions", "sentencePause", "clausePause", "stability", "style", "similarity"):
            voice[key] = float(val) if key in ("speed", "sentencePause", "clausePause", "stability", "style", "similarity") else val
        elif key == "polish":
            voice["polish"] = val.lower() in YES
        elif key == "pronounce":   # pronounce: Parla=Par-la, Weepo=Wee-po
            sc["pronounce"] = {a.strip(): b.strip() for a, b in (pair.split("=", 1) for pair in val.split(",") if "=" in pair)}
        elif key == "size":
            if val.lower() in PRESETS:
                w, h = PRESETS[val.lower()]
                if val.lower() in ("mobile", "phone", "tablet"):
                    sc["mobile"] = True
                    sc["scale"] = 2
            else:
                w, h = re.split(r"\s*[x×*]\s*", val.lower())
            sc["viewport"] = {"width": int(w), "height": int(h)}
        elif key == "hd":
            sc["scale"] = 2 if val.lower() in YES else 1
        elif key == "mobile":
            sc["mobile"] = val.lower() in YES
            if sc["mobile"]:
                sc.setdefault("viewport", {"width": 390, "height": 844}); sc.setdefault("scale", 2)
        elif key == "cookies":
            sc["cookies"] = "dismiss" if val.lower() in YES | {"dismiss", "hide", "decline"} else val
        elif key in ("captions", "gif", "highlightClicks", "progressBar", "frame", "showKeys", "transitions", "chapters"):
            sc[key] = val.lower() in YES
        elif key in ("musicVolume", "gapAfterVoice"):
            sc[key] = float(val)
        elif key == "typeDelay":
            sc[key] = int(re.sub(r"\D", "", val) or 55)
        else:
            sc[key] = val
        i += 1
    if "url" not in sc:
        raise ValueError("the scenario needs a first line like: url: https://your-site.com")
    if voice:
        if "voice" in voice and "engine" not in voice and re.match(r"^[a-z]{2}_[a-z]+([*+][a-z0-9_.*]+)*$", voice["voice"]):
            voice["engine"] = "kokoro"
        if "lang" not in voice and voice.get("engine", "kokoro") == "kokoro" and voice.get("voice"):
            voice["lang"] = {"a": "en-us", "b": "en-gb", "f": "fr-fr", "e": "es", "i": "it", "p": "pt-br", "j": "ja", "z": "cmn", "h": "hi"}.get(voice["voice"][:1], "en-us")
        sc["voice"] = voice
    # Steps: blocks separated by blank lines.
    block = []
    for n, raw in enumerate(lines[i:] + [""], start=i + 1):
        line = raw.strip()
        if line.startswith("//"):
            continue
        if not line:
            if block:
                say = " ".join(l for kind, l in block if kind == "say").strip()
                acts = [a for kind, a in block if kind == "act"]
                step = {"say": say, "actions": acts}
                labels = [l for kind, l in block if kind == "label"]
                cards = [l for kind, l in block if kind == "card"]
                if labels:
                    step["label"] = labels[0]
                if cards:
                    step["card"] = cards[0]
                sc["steps"].append(step)
                block = []
            continue
        if line.startswith("## "):
            block.append(("card", line[3:].strip()))        # full-screen section card ("scene" title)
        elif line.startswith("# "):
            block.append(("label", line[2:].strip()))       # lower-third label shown at the start of the step
        elif line.startswith((">", "-", "*", "→")) and not line.startswith("--"):
            block.append(("act", action(line.lstrip(">-*→ ").strip(), n)))
        else:
            block.append(("say", line))
    if not sc["steps"]:
        raise ValueError("no steps found: write the narration, then '> action' lines, blank line between steps")
    return sc


if __name__ == "__main__":
    try:
        print(json.dumps(parse(open(sys.argv[1], encoding="utf-8").read()), indent=2, ensure_ascii=False))
    except ValueError as e:
        sys.exit(f"scenario error: {e}")
