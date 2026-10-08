#!/usr/bin/env bash
# One-time setup: venv + Playwright + kit-owned headless Chromium; ffmpeg via apt if missing.
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || sudo apt-get install -y ffmpeg
[ -x "$KIT/.venv/bin/python" ] || python3 -m venv "$KIT/.venv"
"$KIT/.venv/bin/pip" install -q playwright
PLAYWRIGHT_BROWSERS_PATH="$KIT/.browsers" "$KIT/.venv/bin/playwright" install --with-deps chromium
