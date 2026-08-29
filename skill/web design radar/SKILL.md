---
name: web-design-radar
description: Use when 用户要求分析获奖或高技术网站首页、逐 Section 解释前端实现、保存 3D/WebGL/Shader 资源，或执行每日 2 站的 Awwwards 复刻研究任务；这是此类任务的首选，取代旧 awwwards-crawler。
---

# Web Design Radar

Produce a durable case pack that lets a later agent perform a 1:1 复刻 of the homepage without pretending inferred behavior is confirmed source code.

The primary deliverable is Chinese Markdown, not a source dump. Publish one `00-网站整体前端技术总结.md` plus a section-by-section set with exactly one detailed Markdown per real homepage Section. HTML, CSS, and JavaScript gathered during analysis are temporary inputs and do not belong to the final deliverable.

## Choose a mode

- **One-off supplied URL:** create or resume a slot `M` run with `scripts/web-design-radar.py start-one-off`, execute its stages, then publish only that run with `scripts/web-design-radar.py finalize-one-off --run-id <RUN_ID>`.
- **Scheduled daily batch:** the coordinator selects exactly two unique sites; isolated slot `A` and `B` workers resume them until closeout.

All state transitions, asset recording, validation, and publication must go through `scripts/web-design-radar.py`. Write working files only under the claimed `stagingDir`; never write directly into a final revision.

## Route by stage

1. Before making technical claims, read [references/evidence-contract.md](references/evidence-contract.md).
2. For `observing`, `extracting`, and final browser QA, read [references/browser-acceptance.md](references/browser-acceptance.md). Use `ego-browser`/ego-lite first.
3. Before acquiring any file, read [references/asset-policy.md](references/asset-policy.md).
4. Before writing section documents, read [references/section-contract.md](references/section-contract.md) and use the matching template.

## Invariants

- Analyze public pages only. Never bypass login, CAPTCHA, DRM, access controls, or obfuscation protection.
- Treat library presence as presence only; effect ownership needs runtime or source evidence.
- Record every claim as `source-confirmed`, `observed`, `inferred`, or `unknown`, linked to evidence.
- 用户可见正文以中文为主；技术标识与代码可以保留英文。一个 Section 对应一个 Markdown，Section 数量必须与真实首页一致。
- 每个 Section 至少保存 4 张不同状态截图；交互、动画、滚动联动或 WebGL Section 还必须保存短视频，并在对应 Markdown 中逐项引用解释。
- Test desktop, mobile, resize, refresh, reduced-motion, resource failure, and WebGL fallback where relevant.
- Preserve public resources needed for replication with URL, purpose, hash, license status, and decoder relationships. Do not silently omit failed downloads.
- Stop browser/network acquisition at 09:00 Asia/Shanghai. A partial, truthful case is preferable to fabricated completeness.
- Chrome/OpenClaw browser is fallback-only and requires a persisted `browserFallbackReason`.
- Finish an ego-lite site run with a dedicated `completeTaskSpace(id, { keep: false })` call after validation confirms the browser task is done.

Scheduled execution details live in [prompts/daily-coordinator.md](prompts/daily-coordinator.md) and [prompts/site-worker.md](prompts/site-worker.md).
Cron declarations must be created disabled with `scripts/declare-crons.py`; enablement is a separate, evidence-gated migration step using the persisted job IDs in `state/automation.json`.
