#!/usr/bin/env bash
# Idempotent setup for demo-video. Safe to run every time.
set -e
C=~/.cache/demo-video; mkdir -p "$C/models" "$C/fonts"
command -v ffmpeg >/dev/null || { echo "ffmpeg missing (apt-get install -y ffmpeg / brew install ffmpeg)"; exit 1; }
if ! node -e "require('playwright')" 2>/dev/null && ! NODE_PATH=$(npm root -g) node -e "require('playwright')" 2>/dev/null; then
  npm install -g playwright >/dev/null 2>&1
  [ -d /opt/pw-browsers ] || npx -y playwright install chromium
fi
python3 -c "import kokoro_onnx, soundfile" 2>/dev/null || pip install -q kokoro-onnx soundfile --break-system-packages 2>/dev/null || pip install -q kokoro-onnx soundfile
R=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
[ -s "$C/models/kokoro-v1.0.onnx" ] || curl -sSL -o "$C/models/kokoro-v1.0.onnx" $R/kokoro-v1.0.onnx
[ -s "$C/models/voices-v1.0.bin" ]  || curl -sSL -o "$C/models/voices-v1.0.bin" $R/voices-v1.0.bin
if [ ! -s "$C/fonts/Inter-Medium.ttf" ]; then
  curl -sSL -o /tmp/inter.zip https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip && \
  unzip -o -q -j /tmp/inter.zip "extras/ttf/Inter-Regular.ttf" "extras/ttf/Inter-Medium.ttf" "extras/ttf/Inter-SemiBold.ttf" -d "$C/fonts" && rm -f /tmp/inter.zip || echo "Inter font unavailable, captions fall back to system sans"
fi
echo "demo-video ready"
