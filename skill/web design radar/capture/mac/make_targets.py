#!/usr/bin/env python3
"""Build ~/web-design-radar-mac/targets.json content for the mac-ego recorder from a headless capture.
Usage: capture/mac/make_targets.py --staging <stagingDir or published case dir> --run-name <name> [--seconds 8] [--consent hide|click]"""
import argparse, json
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--staging", required=True); ap.add_argument("--run-name", required=True)
ap.add_argument("--seconds", type=float, default=8); ap.add_argument("--consent", default="hide", choices=["hide", "click"])
ap.add_argument("--out-dir", default="~/web-design-radar-mac/out", help="output root on the Mac; ~ is expanded there")
a = ap.parse_args()
s = json.loads((Path(a.staging) / "evidence" / "capture-summary.json").read_text())
secs = [{"order": r["order"], "startY": r["start_y"], "endY": r["end_y"]} for r in s.get("recordings", [])]
if not secs:  # fall back to draft index tops
    d = json.loads((Path(a.staging) / "evidence" / "section-index.draft.json").read_text())
    secs = [{"order": e["order"], "startY": max(e["top"] - 270, 0), "endY": e["top"] + max(e["height"] - 900, 0) + 450} for e in d["sections"]]
print(json.dumps({"url": s["url"], "runName": a.run_name, "outDir": a.out_dir, "seconds": a.seconds, "consent": a.consent, "sections": secs}, ensure_ascii=False))
