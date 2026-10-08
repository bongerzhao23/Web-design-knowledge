# Site Worker

You are bound to exactly one slot (`A`, `B`, or manual `M`). All commands run from the kit root. Each stage: claim, do the work, submit, repeat until `ready_to_publish`.

1. Claim once:
   `./wdr claim-stage --slot <SLOT> --owner <OWNER> --json`
   If status is idle, return `IDLE` without capturing anything.
2. Read the stage-routed references in `SKILL.md`. Write only inside the returned `stagingDir`.
   User-facing documents are 中文为主: technical identifiers may remain English, but all explanations are Chinese.
3. **observing** — run the kit capture (its own headless Chromium, fresh cookie-less context; never a desktop/user browser):
   `capture/run.sh --url <siteUrl> --staging <stagingDir> --max-sections 6 --cache-assets` (add `--fast` for a ~3-minute pass)
   It writes desktop `1440×900` and mobile `390×844` screenshots, per-section state shots, 6–12 s native real-time recordings, reduced-motion and no-WebGL shots, lifecycle checks, consent-banner dismissal, direct download of media aborted by headless, console/network errors, asset list, detected libraries (`evidence/capture-summary.json`) and a draft `evidence/section-index.draft.json`. Raw HTML/CSS go to `<stagingDir>/../raw-analysis/` (outside the deliverable).
   Then review the screenshots yourself, correct section boundaries/names, and write the final `evidence/section-index.json` (`order`, Chinese `name`, `document`, `evidenceIds`, ≥4 byte-distinct `screenshots` with `path`/`viewport`/`state`/`trigger`, and `motionCaptureRequired` + `video` or a concrete Chinese `videoOmissionReason`). If `accessWallSuspected` is true, stop: do not bypass login, CAPTCHA, or paywalls.
   Submit with result `{"status":"ok","browserUsed":"playwright-chromium"}`. Only if another browser was genuinely needed set `browserUsed: other-browser` plus a concrete `browserFallbackReason`.
4. **extracting** — read `raw-analysis/` HTML/CSS and the capture summary; record findings as `evidence/EV-<n>.json` and `evidence/claims.json`. Do not keep complete HTML, CSS, or JavaScript bundles in `stagingDir`; they are temporary analysis inputs and do not belong to the final deliverable.
5. **assets** — `capture/record_cached.py --run-id <RUN_ID> --staging <stagingDir> --kinds video --used-by <doc> --limit 1` records cached media; record other needed public assets from `raw-analysis/asset-cache/` with `./wdr record-asset --run-id <RUN_ID> --source-url <url> --input-file <cached-file> --local-path assets/<kind>/<name> --mime <type> --used-by <section-doc> --json`; never bypass authentication, CAPTCHA, paywall, DRM, or protection. Note fonts, models, textures, shaders, decoder dependencies, license (`unknown` if unstated) and failures.
6. **documenting** — create exactly one `00-网站整体前端技术总结.md` and one `sections/NN-中文名称.md` for every Section using the templates; meet the depth gate in `references/section-contract.md`. Embed every declared screenshot and link every recording with Chinese explanation.
7. **validating** — `./wdr validate-case --revision <stagingDir> --json` until `passed: true`, then submit.
8. Submit exactly once per stage on success:
   `./wdr submit-stage --run-id <RUN_ID> --stage <STAGE> --owner <OWNER> --result <absolute-json-path> --json`
9. On failure, submit exactly once:
   `./wdr fail-stage --run-id <RUN_ID> --stage <STAGE> --owner <OWNER> --error-class <CLASS> --message <SANITIZED> --json`

Daily slots: at or after 09:00 Asia/Shanghai stop new network/browser acquisition and let closeout preserve a partial case.

For manual slot `M`, after validating reaches `ready_to_publish`, call `./wdr finalize-one-off --run-id <RUN_ID> --json` and report success only when it returns `published: true`. Daily slots remain owned by `finalize-day`.

Return only one internal marker: `IDLE|OK|PARTIAL`.
