# Browser Acceptance

Use `ego-browser` (ego-lite) first. Create one isolated task space per site and reuse its numeric `taskSpaceId` through every stage. Task spaces may inherit login state, but this workflow visits public pages only and never records authentication state.

Default viewports are desktop `1440×900` and mobile `390×844`. Wait for the loader, traverse the full homepage, and capture each interaction section at meaningful start/process/end states. Record console errors, failed requests, WebGL/WebGPU capabilities, fallbacks, and actual viewport dimensions.

## Per-Section visual capture

For every Section, save at least four meaningful screenshots under `screenshots/NN-name/`:

1. desktop initial/rest state;
2. desktop interaction or scroll process state;
3. desktop end/exit/alternate state;
4. mobile representative or active state.

Do not create four near-identical screenshots. Record each file's viewport, visible state, and exact trigger in `evidence/section-index.json`. Add more screenshots when one interaction has several visually distinct phases.

If a Section contains entrance/loop animation, hover, pointer/touch response, drag, scroll-linked motion, video state changes, WebGL, 3D, or Shader behavior, save one focused 6–12 second recording under `recordings/`. Begin from rest, perform the real input at human-readable speed, hold the changed state briefly, and show the release/exit when relevant. A genuinely static Section may omit video only with a concrete Chinese `videoOmissionReason`.

ego-lite remains the browser controller. For recording, try a short CDP screencast probe only when ego-lite exposes frames and acknowledgements. Otherwise capture a timestamped CDP screenshot sequence while ego-lite drives the real pointer/touch/scroll path, then encode it to H.264 MP4 with ffmpeg at a useful cadence (target 10–15 fps). Record `captureMethod` as `ego-lite-cdp-screencast` or `ego-lite-frame-sequence`. Failure of recording alone does not authorize Chrome fallback; use Chrome only under the existing persisted `browserFallbackReason` contract.

The deterministic fallback uses raw CDP frames from the selected ego-lite tab. Save frames in a temporary directory outside the case, copy only the encoded MP4 into `recordings/`, and remove the temporary frames after the MP4 signature and duration are verified:

```js
const fs = await import('node:fs/promises')
for (let i = 0; i < frameCount; i += 1) {
  // Drive one small pointer/scroll step here before capturing the next visual state.
  const shot = await cdp('Page.captureScreenshot', { format: 'png', fromSurface: true })
  await fs.writeFile(`${temporaryFrames}/frame-${String(i).padStart(4, '0')}.png`, Buffer.from(shot.data, 'base64'))
}
```

```bash
ffmpeg -framerate 12 -i 'frame-%04d.png' -c:v libx264 -pix_fmt yuv420p -movflags +faststart section-interaction.mp4
```

Do not treat a slideshow of duplicate frames as a recording. The sequence must contain the real initial state, input progression, visible response, and end/release state.

Every screenshot must be embedded in its matching Section Markdown with a Chinese caption. Every video must be linked there with a Chinese description of the input path and visible state changes. Media stored but not referenced by the document is incomplete evidence.

At minimum verify:

- desktop and mobile layout/interaction;
- one full scroll, pointer/hover/touch behavior, and scroll-linked states;
- refresh, resize, leave/return lifecycle, and cleanup/dispose behavior;
- reduced-motion and WebGL/resource failure fallbacks.

Prefer semantic snapshots for DOM controls and screenshot/CDP inspection for canvas. Keep source observation separate from browser inference.

If ego-lite first execution fails because the runtime is unavailable, follow the ego-browser installation reference. Use OpenClaw/Chrome only when ego-lite still cannot perform the required operation; persist the concrete `browserFallbackReason` before submitting the stage.

If the user takes control, or the task space becomes user-owned/inactive, stop immediately. Resume only after explicit confirmation and claim/take over the same ID. After a prior call confirms browser work is complete, use a separate final invocation:

```js
await completeTaskSpace(id, { keep: false })
```
