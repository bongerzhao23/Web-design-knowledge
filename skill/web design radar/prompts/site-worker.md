# Site Worker

You are bound to exactly one slot (`A`, `B`, or manual `M`). Run one stage, checkpoint it, and exit so later workers can resume safely.

1. Claim once:
   `python3.11 scripts/web-design-radar.py claim-stage --slot <SLOT> --owner <OWNER> --json`
   If status is idle, return `IDLE` without opening a browser.
2. Read the stage-routed references in `SKILL.md`. Write only inside the returned `stagingDir`.
   User-facing documents are 中文为主: technical identifiers may remain English, but all explanations are Chinese.
3. For browser work, use `ego-browser` before any OpenClaw/Chrome fallback. Create one task space for the site on the first stage; on later stages reuse the exact numeric `taskSpaceId`. Persist it in the stage result. Visit public pages only.
4. If ego-lite fails to support the needed operation, Chrome is permitted only as a fallback. The result must set `browserUsed: openclaw-chrome` and a concrete `browserFallbackReason`; otherwise submission is invalid.
5. Observe desktop `1440×900` and mobile `390×844`, loader, full scroll, pointer/touch states, resize, refresh, return, reduced-motion, console/network errors, resource failures, cleanup, and fallback. Label facts `source-confirmed`, `observed`, `inferred`, or `unknown` and link evidence IDs.
   During `observing`, write `evidence/section-index.json` in actual top-to-bottom order with `order`, Chinese `name`, target `document`, and `evidenceIds` for every visually or narratively distinct homepage Section. For each Section add at least four byte-distinct screenshot records (`path`, `viewport`, `state`, `trigger`). Set `motionCaptureRequired`; when true add a real, playable 6–12 second `video` record with `path`, ffprobe-backed `durationSeconds`, `captureMethod`, and the complete `interaction`. When false add a concrete Chinese `videoOmissionReason`.
   Follow `references/browser-acceptance.md` for ego-lite CDP screencast/frame-sequence recording. Screenshot or recording failure alone does not authorize Chrome fallback. Embed and explain every declared capture in the matching Chinese Section Markdown.
6. Record public assets with `record-asset`; never bypass authentication, CAPTCHA, paywall, DRM, or protection. Map models, textures, shaders, fonts, decoder dependencies, license, hashes, usage, and failures.
   During extraction, do not retain complete HTML, CSS, or JavaScript bundles in `stagingDir`; they are temporary analysis inputs and do not belong to the final deliverable.
7. During `documenting`, enumerate the homepage's actual visual/narrative sections from top to bottom. Create exactly one `00-网站整体前端技术总结.md`, then one detailed `sections/NN-中文名称.md` for every Section. Use the templates and meet the depth gate in `references/section-contract.md`; do not create separate thin architecture or replica-prompt documents.
8. Submit exactly once on success:
   `python3.11 scripts/web-design-radar.py submit-stage --run-id <RUN_ID> --stage <STAGE> --owner <OWNER> --result <absolute-json-path> --json`
9. On failure, submit exactly once:
   `python3.11 scripts/web-design-radar.py fail-stage --run-id <RUN_ID> --stage <STAGE> --owner <OWNER> --error-class <CLASS> --message <SANITIZED> --json`

At or after 09:00 Asia/Shanghai, stop new network/browser acquisition and let closeout preserve a partial case. If control becomes user-owned/inactive, stop and wait for explicit user confirmation; do not route around it.

When the validating stage has passed and a prior ego-lite call confirms browser work is complete, make a dedicated final ego-browser call containing `await completeTaskSpace(id, { keep: false })`. Do not leave tabs or task spaces behind.

For manual slot `M`, after validating reaches `ready_to_publish`, call `finalize-one-off --run-id <RUN_ID>` and report success only when it returns `published: true`. Daily slots remain owned by `finalize-day`.

Return only one internal marker: `IDLE|OK|PARTIAL`.
