#!/usr/bin/env python3
"""Draft a scenario from a URL alone: open the page, read what's on it, write a starting scenario.txt.

Usage: python3 draft.py https://app.example.com OUT_DIR [lang]
Writes OUT_DIR/explore.png + explore.json (what the page contains) and OUT_DIR/draft-scenario.txt:
settings filled from the page (title, subtitle, outro, qr), a hook step, then one step per prominent
heading / button so the narration and actions only need editing, not inventing.
The draft is a starting point for a human or an agent — every "TODO" line must be rewritten or removed.
"""
import json, os, re, subprocess, sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
URL, OUT = sys.argv[1], sys.argv[2]
LANG = sys.argv[3] if len(sys.argv) > 3 else ""
D = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

# 1. Explore the page with the recorder (one empty step, no capture).
json.dump({"url": URL, "steps": [{"say": "", "actions": []}]}, open(f"{OUT}/draft.json", "w"))
r = subprocess.run(["node", f"{D}/record.js", f"{OUT}/draft.json", OUT, "--explore=0"], capture_output=True, text=True)
if r.returncode or not os.path.exists(f"{OUT}/explore.json"):
    sys.exit((r.stdout + r.stderr).strip() or "explore failed")
p = json.load(open(f"{OUT}/explore.json"))

# 2. Settings from the page.
site = re.sub(r"^www\.", "", re.sub(r"^https?://", "", URL).split("/")[0])
title = (p.get("title") or site).split(" | ")[0].split(" — ")[0].split(" - ")[0].strip()[:40]
desc = (p.get("description") or "").strip()
subtitle = (desc.split(". ")[0])[:60] if desc else ""
lang = LANG or (p.get("lang") or "en")[:2].lower()
voice = {"fr": "ff_siwis", "es": "ef_dora", "it": "if_sara", "pt": "pf_dora", "ja": "jf_alpha", "zh": "zf_xiaoxiao", "hi": "hf_alpha"}.get(lang, "af_heart")
heads = [h["text"] for h in p.get("headings", []) if 3 <= len(h["text"]) <= 60 and h["level"] <= 2]
heads = list(dict.fromkeys(heads))          # keep order, drop duplicates
buttons = [b for b in p.get("buttons", []) if 2 <= len(b) <= 30 and not re.search(r"cookie|accept|reject|decline|consent|sign in|log in|login|menu|close", b, re.I)]
fields = p.get("fields", [])
cta = next((b for b in p.get("buttons", []) if re.search(r"start|try|sign up|get|demo|free|book|buy|download", b, re.I)), None)

out = [f"// Draft made by draft.py from {URL} — edit every line, delete what you don't need.",
       "// Narration = normal lines (say why it matters, 6-20 words). Actions = lines starting with '>'.",
       f"url: {URL}", "template: launch", f"voice: {voice}", f"title: {title}"]
if subtitle:
    out.append(f"subtitle: {subtitle}")
out += [f"outro: {cta + ' at ' + site if cta else 'Try it at ' + site}", f"qr: {URL}", "music: auto", "cookies: dismiss", ""]
out += [f"## {title}", "", f"# {heads[0] if heads else 'Overview'}",
        f"TODO hook: what {title} does in one sentence" + (f" (page says: {desc[:90]})" if desc else "") + ".", "> wait 1s", ""]
n = 0
for h in heads[1:6]:
    n += 1
    out += [f"# {h[:32]}", f"TODO why this matters: {h}.", f"> scroll to \"{h}\"", "> wait 1s", ""]
if fields[:1]:
    out += ["## Try it", "", "# Search", f"TODO: type something meaningful into \"{fields[0]}\".", f"> type \"TODO\" into \"{fields[0]}\"", "> press Enter", "> wait 1s", ""]
for b in buttons[:2]:
    out += [f"# {b}", f"TODO what happens after \"{b}\".", f"> click \"{b}\"", "> wait 1s", ""]
out += ["# Wrap-up", f"TODO takeaway: the one thing to remember about {title}.", f"> highlight \"{cta}\"" if cta else "> wait 1s", ""]
open(f"{OUT}/draft-scenario.txt", "w").write("\n".join(out))
print(f"draft: {OUT}/draft-scenario.txt   ({len(heads)} headings, {len(buttons)} buttons, {len(fields)} fields seen; screenshot {OUT}/explore.png)")
print("Next: replace every TODO line, remove steps that don't show an outcome, check targets with --explore, then make.sh.")
