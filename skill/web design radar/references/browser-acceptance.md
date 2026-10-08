# Browser Acceptance

Use the kit capture script `capture/run.sh` (Playwright + kit-owned headless Chromium under `.browsers/`). Every viewport uses a fresh context with no cookies or storage; it never attaches to an existing desktop browser. This workflow visits public pages only and never records authentication state.

Default viewports are desktop `1440×900` and mobile `390×844`. The script waits for load (networkidle + 4 s for loaders), wheel-scrolls the full homepage in viewport steps, and for each detected Section captures desktop entering / rest / pointer-moved / scroll-through states plus one mobile representative state. It records console errors, failed requests, WebGL/WebGPU capabilities, canvas inventory, fonts, network assets and library presence in `evidence/capture-summary.json`.

Headless Chromium renders WebGL with SwiftShader (software). Frame rates are lower than on a real GPU and heavy shaders may look simplified; state this limitation in documents instead of guessing.

## Per-Section visual capture

For every Section, keep at least four meaningful screenshots under `screenshots/NN-name/`:

1. desktop initial/rest state;
2. desktop interaction or scroll process state;
3. desktop end/exit/alternate state;
4. mobile representative or active state.

Do not declare four near-identical screenshots (the validator rejects byte duplicates). Record each file's viewport, visible state, and exact trigger in `evidence/section-index.json`. Mobile shots locate the same DOM element (stable selector) as the desktop Section; only when it is hidden on mobile does the script fall back to a document-height ratio (`mobile.matched: false`).

If a Section contains entrance/loop animation, hover, pointer/touch response, drag, scroll-linked motion, video state changes, WebGL, 3D, or Shader behavior, keep one focused 6–12 second recording under `recordings/`. The kit records with `captureMethod: playwright-record-video`: a separate desktop context with Playwright's native `record_video` runs alone after the screenshot phase, scrolls with an in-page `requestAnimationFrame` easeInOut over real wall time while the pointer moves every ~100 ms, then each Section segment is cut from the session video and encoded H.264 MP4 at 25 fps, equivalent to:

```bash
ffmpeg -ss <start> -i session.webm -t <seconds> -vf fps=25 -c:v libx264 -pix_fmt yuv420p -movflags +faststart section.mp4
```

`capture-summary.json#recordings` reports `uniqueFrames`, `effectiveFps` (distinct frames per second, via mpdecimate) and `pageFps` (requestAnimationFrame rate in the page). On a CPU-only machine heavy WebGL Sections still drop to roughly 7–15 effective fps; say so in documents. When the Mac Ego Lite backend records the Sections instead (see `SKILL.md`), the video records carry `captureMethod: ego-lite-cdp-screencast` and the stage result uses `browserUsed: ego-lite`. A genuinely static Section may omit video only with a concrete Chinese `videoOmissionReason`. Screenshot or recording failure alone does not authorize another browser; use `browserUsed: other-browser` only with a persisted `browserFallbackReason`.

Consent banners are handled before every capture: known CMP buttons (OneTrust, Cookiebot, Didomi, Usercentrics, Quantcast, TrustArc, Iubenda, CookieYes, Osano, Webflow/Finsweet, …) and generic accept-type buttons in many languages inside a cookie/privacy context, including iframes, are clicked; labels matching login/subscribe/register are never clicked. Remaining fixed overlays with consent wording are hidden via CSS. Everything is logged in `capture-summary.json#consent`.

Every screenshot must be embedded in its matching Section Markdown with a Chinese caption. Every video must be linked there with a Chinese description of the input path and visible state changes. Media stored but not referenced by the document is incomplete evidence.

At minimum verify:

- desktop and mobile layout/interaction;
- one full scroll, pointer/hover behavior, and scroll-linked states;
- reduced-motion (`screenshots/_global/desktop-reduced-motion.png`) and no-WebGL (`screenshots/_global/desktop-no-webgl.png`) fallbacks;
- resize desktop→mobile→desktop, leave/return (visibility or CDP freeze/resume) and reload — automated in `capture-summary.json#lifecycle` with canvas state and error counts, screenshots in `screenshots/_global/lifecycle/`.

Keep source observation separate from browser inference. If the page shows a login, CAPTCHA, or paywall (`accessWallSuspected`), stop and report; never bypass it.
