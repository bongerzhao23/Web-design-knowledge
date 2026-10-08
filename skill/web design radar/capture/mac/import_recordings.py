#!/usr/bin/env python3
"""After the mac-ego recordings were copied into <stagingDir>/mac-import/ (mac-record-summary.json + recordings/*.mp4),
replace the staging recordings and patch evidence/section-index(.draft).json video entries (captureMethod ego-lite-cdp-screencast).
Usage: capture/mac/import_recordings.py --staging <stagingDir>"""
import argparse, json, shutil
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--staging", required=True); a = ap.parse_args()
st = Path(a.staging); imp = st / "mac-import"
summ = json.loads((imp / "mac-record-summary.json").read_text())
by = {r["order"]: r for r in summ["sections"] if not r.get("error")}
for r in by.values():
    shutil.copy2(imp / r["path"], st / r["path"])
for name in ("section-index.json", "section-index.draft.json"):
    p = st / "evidence" / name
    if not p.exists():
        continue
    idx = json.loads(p.read_text())
    for e in idx["sections"]:
        r = by.get(e["order"])
        if r and isinstance(e.get("video"), dict):
            e["video"].update({"path": r["path"], "durationSeconds": r["durationSeconds"], "captureMethod": "ego-lite-cdp-screencast",
                               "interaction": f"Mac ego-lite（Apple GPU）CDP screencast：从 y={r['startY']} 按真实时间 easeInOut 滚动到 y={r['endY']}，指针同步移动；有效 {r['effectiveFps']} fps，页面 rAF {r['pageFps']} fps"})
    p.write_text(json.dumps(idx, ensure_ascii=False, indent=2))
shutil.rmtree(imp)
print(json.dumps({"imported": sorted(by), "browserUsed": "ego-lite"}))
