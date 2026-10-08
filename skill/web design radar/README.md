# Web Design Radar

Evidence-backed homepage analysis → Chinese Markdown case pack for 1:1 replication. Capture runs with a kit-owned headless Chromium (Playwright); it never attaches to a user's browser, never stores cookies or credentials, public pages only. Section recordings can optionally run on a Mac with Ego Lite for real GPU frame rates.

Agent-facing instructions: `SKILL.md` (Chinese). Contracts: `references/`, `templates/`, `contracts/`, `prompts/`.

## Layout

| Path | What |
|---|---|
| `wdr` | CLI wrapper → `scripts/web-design-radar.py` (state machine, assets, validation, publishing; stdlib only) |
| `capture/run.sh` → `capture/capture.py` | Headless capture (asyncio Playwright) |
| `capture/capture_lib.py` | Pure helpers: consent label rules, asset classification, URL redaction, section choice, range plan |
| `capture/record_cached.py` | Record cached assets (e.g. downloaded videos) via `wdr record-asset` |
| `setup.sh` | venv + Playwright + Chromium into `.venv/` and `.browsers/`; ffmpeg via apt if missing |
| `capture/mac/` | mac-ego recording backend: `ego_record.mjs` (runs in Ego Lite), `make_targets.py`, `import_recordings.py` |
| `scripts/declare-crons.py` | Optional OpenClaw cron declarations for the daily batch (created disabled) |
| `run_tests.sh` | Unit tests (`tests/`) |
| archive | `WEB_DESIGN_RADAR_ROOT`, default `~/Desktop/Web Design Radar/`, or `./archive/` when there is no `~/Desktop`: `state/` (SQLite + staging) and published case packs. Git-ignored. |

## Quick start (one-off)

```bash
./setup.sh && ./run_tests.sh && ./wdr init --json
./wdr start-one-off --url https://example.com --source-url https://www.awwwards.com/sites/example --json   # add --rerun to redo a finished site today
./wdr claim-stage --slot M --owner me --json                     # observing
capture/run.sh --url https://example.com --staging <stagingDir> --cache-assets [--fast]
# write evidence/section-index.json, then submit; repeat claim/submit for extracting, assets, documenting, validating
./wdr validate-case --revision <stagingDir> --json
./wdr finalize-one-off --run-id <RUN_ID> --json                   # must return published: true
```

## Capture pipeline

1. Desktop (1440×900), mobile (390×844, DPR 2, touch) and variants (reduced-motion, no-WebGL browser) run in parallel; consent banners are dismissed in each context first.
2. Desktop: stepwise screenshots, DOM full-width block detection (`section/header/footer`, background change, height thresholds, pinned negative tops clipped), 4 state shots per Section, raw HTML/CSS to `raw-analysis/`, then lifecycle checks (resize→mobile→desktop, hidden/visible via other tab or CDP freeze/resume, reload) with canvas state and error counts.
3. Mobile: same DOM selector per Section (ratio fallback only if hidden).
4. Recording (alone, for CPU): native `record_video`, in-page rAF easeInOut scroll over real time + pointer path; per-Section MP4 cut at 25 fps; reports `uniqueFrames`, `effectiveFps`, `pageFps`.
5. Media aborted by headless is fetched directly (Range header, `--media-cap-mb`, default 60) into `raw-analysis/asset-cache/`.

### Flags

`--max-sections 6`, `--video-seconds 8`, `--record-width 1280`, `--fast`, `--no-video`, `--cache-assets`, `--no-media-download`, `--media-cap-mb 60`, `--timeout 45000`.

## Measured on a Linux server (8 vCPU, no GPU; noth.in, 6 Sections)

| | v1 | v2 normal | v2 `--fast` |
|---|---|---|---|
| Total capture time | ~380 s | 288 s | 185 s |
| Recording effective fps | 0.6–4.2 (screenshot frames) | 6.8–15.9 | 6.8–17.1 |
| In-page rAF fps while recording | n/a | 7–56 | — |

No `/dev/dri`, no `nvidia-smi`: all GL flag variants (`--use-angle=swiftshader|vulkan`, `--use-gl=egl`, new headless) resolve to SwiftShader and gave the same idle 60 fps, so the gain comes from native recording and running it alone, not from GL flags.

## Limits

- CPU-only WebGL: heavy shader Sections record at ~7–15 distinct fps.
- Visibility "hidden" cannot be produced in headless tabs; the check uses CDP `Page.setWebLifecycleState` freeze/resume and says so.
- Consent: accept-type only, in a throwaway context; unknown custom banners fall back to CSS hiding by wording.
- Section detection is heuristic; the agent must review and rename Sections before documenting.

## Recording backends: mac-ego (default when the user's Mac is reachable) / headless (fallback)

`capture/mac/ego_record.mjs` runs on a Mac with Ego Lite (`ego-browser nodejs`), inside ONE agent-owned TaskSpace (never the user's tabs), at 1440×900 via `Emulation.setDeviceMetricsOverride`. For each Section target it scrolls in-page (rAF easeInOut, real time) with pointer motion, records `Page.startScreencast` frames (acked), and encodes VFR H.264 MP4 from the real frame timestamps with `/opt/homebrew/bin/ffmpeg`. It writes start/end screenshots, `mac-record-summary.json` (`effectiveFps`, `pageFps`, renderer, consent) and closes the space with `finish({ keep: [] })`. Outputs: `~/web-design-radar-mac/out/<runName>/`.

Consent default is `"hide"` (CSS only, no click), because a TaskSpace uses the user's Ego Lite profile and a click would store a consent choice there. Use `"click"` only with the user's OK.

Default when the agent can run commands on the user's Mac with Ego Lite; otherwise use the headless recording. Ego Lite upgrades (`[ego-browser:notice]`) require the user's consent.

Workflow (agent with Mac Shell access; 1 approval per Mac command):
1. Capture machine: `python3 capture/mac/make_targets.py --staging <stagingDir> --run-name <name> > targets.json` (targets from the headless recording phase, or estimated from the draft section index).
2. Mac, one command: heredoc `capture/mac/ego_record.mjs` to `~/web-design-radar-mac/ego_record.mjs` and the targets JSON to `~/web-design-radar-mac/targets.json`, then `ego-browser nodejs < ~/web-design-radar-mac/ego_record.mjs` (ego-browser does not forward env vars; the script reads `targets.json` from that fixed path). Guard with a background PID + 300 s loop (macOS has no `timeout`).
3. Copy `~/web-design-radar-mac/out/<name>/{mac-record-summary.json,recordings/*.mp4}` back to the capture machine into `<stagingDir>/mac-import/` (summary at top level, MP4s under `recordings/`), with the agent platform's file copy tool or scp.
4. Capture machine: `capture/mac/import_recordings.py --staging <stagingDir>` (replaces recordings, sets `captureMethod: ego-lite-cdp-screencast`), and submit the observing stage with `{"status":"ok","browserUsed":"ego-lite"}`.

Measured (noth.in, M2 Pro, Metal ANGLE): effective 75–99 fps, page rAF 95–119 fps per Section, vs 6.8–15.9 fps headless on the GPU-less server.
