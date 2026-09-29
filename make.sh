#!/usr/bin/env bash
# Full pipeline: narration -> selector check -> recording -> final MP4 -> review sheet.
# Usage: make.sh scenario.txt|scenario.json OUT_DIR [output.mp4]
set -e
D="$(cd "$(dirname "$0")" && pwd)"; S="$1"; O="$2"; F="${3:-$O/demo.mp4}"
export NODE_PATH="$(npm root -g)"
mkdir -p "$O"; rm -f "$O/durations.json"; rm -rf "$O/audio"
case "$S" in *.txt|*.md) python3 "$D/scenario.py" "$S" > "$O/scenario.json"; S="$O/scenario.json";; esac
echo "== 1/5 narration";  python3 "$D/tts.py" "$S" "$O"
echo "== 2/5 dry run";    node "$D/record.js" "$S" "$O" --dry
echo "== 3/5 recording";  node "$D/record.js" "$S" "$O"
echo "== 4/5 mixing";     python3 "$D/mix.py" "$S" "$O" "$F"
echo "== 5/5 review";     python3 "$D/check.py" "$O" "$F"
