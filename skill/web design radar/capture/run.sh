#!/usr/bin/env bash
# Usage: capture/run.sh --url <public-url> --staging <stagingDir> [--max-sections 6] [--video-seconds 8] [--no-video] [--cache-assets]
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
export PLAYWRIGHT_BROWSERS_PATH="$KIT/.browsers"
exec "$KIT/.venv/bin/python" "$KIT/capture/capture.py" "$@"
