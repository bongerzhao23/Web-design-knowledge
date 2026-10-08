# Daily Coordinator

Operate the Asia/Shanghai daily selection with `quota=2`. Daily mode is driven by the agent's own scheduled routine; this kit does not create cron jobs.

1. Use the agent's web search (and plain fetches of public pages) on Awwwards first — Site of the Day / Developer Award / recent nominees — for popular or technically ambitious homepages, emphasizing renewable/new energy, GSAP, Three.js, 3D, shader, WebGL, and WebGPU. Open each Awwwards `/sites/<slug>` page and take the "Visit Site" link as `siteUrl`. Search only public pages.
2. If Awwwards is unavailable, use reputable award/gallery or direct public-site sources and set `sourceStatus` to a concrete degraded value; never imply primary-source success.
3. Normalize URLs, exclude domains already selected for the date, score technology/industry/popularity/novelty/analyzability, and keep diversity between the two sites.
4. Write a top-level candidate object matching `contracts/candidate-list.schema.json`. It must contain at least two unique valid domains before batch creation.
5. Call `./wdr start-batch --date <YYYY-MM-DD> --candidates <absolute-json-path> --json` once from the kit root. Repeated calls resume the same A/B run and must never claim a third site.
6. Run slot A then slot B with the site-worker procedure (sequentially is fine). Do not browse target sites in the coordinator.
7. After both slots reach `ready_to_publish` (or the 09:00 deadline), call `./wdr finalize-day --date <YYYY-MM-DD> --json`.

Return an internal status only: `OK` after dispatch, `PARTIAL` for truthful source degradation, or `IDLE` if the batch already exists or the deadline prevents work.
