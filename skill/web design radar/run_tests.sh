#!/usr/bin/env bash
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
cd "$KIT/tests" && python3 -m unittest discover -s . "$@"
