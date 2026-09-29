#!/usr/bin/env bash
# Full pipeline: narration -> selector check -> recording -> final MP4.
# Usage: make.sh scenario.json OUT_DIR [output.mp4]
set -e
D="$(cd "$(dirname "$0")" && pwd)"; S="$1"; O="$2"; F="${3:-$O/demo.mp4}"
export NODE_PATH="$(npm root -g)"
mkdir -p "$O"; rm -f "$O/durations.json"; rm -rf "$O/audio"
echo "== 1/4 narration";  python3 "$D/tts.py" "$S" "$O"
echo "== 2/4 dry run";    node "$D/record.js" "$S" "$O" --dry
echo "== 3/4 recording";  node "$D/record.js" "$S" "$O"
echo "== 4/4 mixing";     python3 "$D/mix.py" "$S" "$O" "$F"
