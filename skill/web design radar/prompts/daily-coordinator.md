# Daily Coordinator

Operate the Asia/Shanghai daily selection with `quota=2`.

1. Search Awwwards first for popular or technically ambitious homepages, emphasizing renewable/new energy, GSAP, Three.js, 3D, shader, WebGL, and WebGPU. Use `agent-reach` first and OpenCLI second. Search only public pages.
2. If Awwwards is unavailable, use reputable award/gallery or direct public-site sources and set `sourceStatus` to a concrete degraded value; never imply primary-source success.
3. Normalize URLs, exclude domains already selected for the date, score technology/industry/popularity/novelty/analyzability, and keep diversity between the two sites.
4. Write a top-level candidate object matching `contracts/candidate-list.schema.json`. It must contain at least two unique valid domains before batch creation.
5. Call `python3.11 scripts/web-design-radar.py start-batch --date <YYYY-MM-DD> --candidates <absolute-json-path> --json` once. Repeated calls resume the same A/B run and must never claim a third site.
6. Dispatch one isolated worker bound to slot A and one to slot B. Do not browse target sites in the coordinator.

Return an internal status only: `OK` after dispatch, `PARTIAL` for truthful source degradation, or `IDLE` if the batch already exists or the deadline prevents work.
