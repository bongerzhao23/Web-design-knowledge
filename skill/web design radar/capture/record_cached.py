#!/usr/bin/env python3
"""Record cached assets from capture-summary.json into the run's asset manifest via ./wdr record-asset.
Usage: capture/record_cached.py --run-id RUN --staging DIR --kinds video,font --used-by sections/01-x.md [--limit 5]"""
import argparse, json, mimetypes, subprocess, sys
from pathlib import Path
KIT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--run-id", required=True); ap.add_argument("--staging", required=True)
ap.add_argument("--kinds", default="video"); ap.add_argument("--used-by", action="append", required=True); ap.add_argument("--limit", type=int, default=10)
a = ap.parse_args()
s = json.loads((Path(a.staging) / "evidence/capture-summary.json").read_text())
kinds = set(a.kinds.split(",")); done = 0
for r in s["assets"]:
    if r["kind"] not in kinds or not r.get("cachedFile") or done >= a.limit: continue
    f = Path(r["cachedFile"]); name = f.name.split("-", 1)[1]
    mime = (r.get("contentType") or mimetypes.guess_type(name)[0] or "application/octet-stream").split(";")[0]
    cmd = [sys.executable, str(KIT / "scripts/web-design-radar.py"), "record-asset", "--run-id", a.run_id, "--source-url", r["url"],
           "--input-file", str(f), "--local-path", f"assets/{r['kind']}s/{name}", "--mime", mime, "--json"]
    for u in a.used_by: cmd += ["--used-by", u]
    print(subprocess.run(cmd, capture_output=True, text=True).stdout.strip()[:200]); done += 1
