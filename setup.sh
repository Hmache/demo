#!/usr/bin/env bash
# Idempotent setup for demo-video. Safe to run every time.
set -e
C=~/.cache/demo-video; mkdir -p "$C/models" "$C/fonts"
command -v ffmpeg >/dev/null || { echo "ffmpeg missing (apt-get install -y ffmpeg / brew install ffmpeg)"; exit 1; }
if ! node -e "require('playwright')" 2>/dev/null && ! NODE_PATH=$(npm root -g) node -e "require('playwright')" 2>/dev/null; then
  npm install -g playwright >/dev/null 2>&1 || { mkdir -p "$C/node" && (cd "$C/node" && npm init -y >/dev/null 2>&1 && npm install playwright >/dev/null 2>&1) && echo "playwright installed in $C/node (export NODE_PATH=$C/node/node_modules)"; }
fi
# A browser: Playwright's own download, or (when its CDN is blocked) a portable ungoogled-chromium from GitHub releases.
if [ -z "$CHROMIUM_PATH" ] && [ ! -d /opt/pw-browsers ] && ! ls "$HOME/.cache/ms-playwright" 2>/dev/null | grep -q chromium; then
  NODE_PATH="${NODE_PATH:-$C/node/node_modules}" npx -y playwright install chromium >/dev/null 2>&1 || {
    ARCH=$(uname -m); case "$ARCH" in aarch64|arm64) A=arm64;; *) A=x64;; esac
    if [ ! -x "$C/chromium/chrome" ]; then
      echo "Playwright's browser CDN is blocked; fetching portable ungoogled-chromium ($A) from GitHub..."
      URL=$(curl -sS "https://api.github.com/repos/ungoogled-software/ungoogled-chromium-portablelinux/releases?per_page=1" | python3 -c "import sys,json;print([a['browser_download_url'] for a in json.load(sys.stdin)[0]['assets'] if a['name'].endswith('${A}_linux.tar.xz')][0])")
      mkdir -p "$C/chromium" && curl -sSL "$URL" | tar -xJ --strip-components=1 -C "$C/chromium"
    fi
    # missing X libraries (e.g. libXdamage) are stubbed: headless Chromium never calls them
    mkdir -p "$C/stublib"
    for lib in $(ldd "$C/chromium/chrome" 2>/dev/null | awk '/not found/{print $1}'); do
      printf 'int XDamageQueryExtension(void*a,int*b,int*c){return 0;}int XDamageQueryVersion(void*a,int*b,int*c){return 0;}unsigned long XDamageCreate(void*a,unsigned long b,int c){return 0;}void XDamageDestroy(void*a,unsigned long b){}void XDamageSubtract(void*a,unsigned long b,unsigned long c,unsigned long d){}void XDamageAdd(void*a,unsigned long b,unsigned long c){}\n' > "$C/stublib/stub.c"
      gcc -shared -fPIC -o "$C/stublib/$lib" "$C/stublib/stub.c" 2>/dev/null && echo "stubbed $lib"
    done
    echo "browser: $C/chromium/chrome  (export CHROMIUM_PATH=$C/chromium/chrome LD_LIBRARY_PATH=$C/stublib)"
  }
fi
python3 -c "import kokoro_onnx, soundfile, qrcode, PIL" 2>/dev/null || pip install -q kokoro-onnx soundfile qrcode pillow --break-system-packages 2>/dev/null || pip install -q kokoro-onnx soundfile qrcode pillow
R=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
[ -s "$C/models/kokoro-v1.0.onnx" ] || curl -sSL -o "$C/models/kokoro-v1.0.onnx" $R/kokoro-v1.0.onnx
[ -s "$C/models/voices-v1.0.bin" ]  || curl -sSL -o "$C/models/voices-v1.0.bin" $R/voices-v1.0.bin
if [ ! -s "$C/fonts/Inter-Medium.ttf" ]; then
  curl -sSL -o /tmp/inter.zip https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip && \
  unzip -o -q -j /tmp/inter.zip "extras/ttf/Inter-Regular.ttf" "extras/ttf/Inter-Medium.ttf" "extras/ttf/Inter-SemiBold.ttf" -d "$C/fonts" && rm -f /tmp/inter.zip || echo "Inter font unavailable, captions fall back to system sans"
fi
echo "demo-video ready"
