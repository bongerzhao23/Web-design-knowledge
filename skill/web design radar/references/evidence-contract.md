# Evidence Contract

Use evidence IDs to keep facts separate from interpretations. Store individual evidence records under `evidence/EV-<n>.json` and aggregate claims in `evidence/claims.json`.

## Confidence labels

- `source-confirmed`: directly supported by readable source, sourcemap, shader text, or an asset graph.
- `observed`: directly reproduced in the live browser or captured network/runtime state.
- `inferred`: an equivalent implementation or likely mechanism supported by behavior but not confirmed in source.
- `unknown`: insufficient evidence; state the missing observation.

Detecting GSAP, Three.js, Lenis, or another library proves only presence. Assigning an effect to it requires a relevant timeline, call site, property mutation, runtime trace, or source symbol.

## Evidence record

```json
{
  "id": "EV-12",
  "sourceType": "runtime-behavior",
  "source": "recordings/hero-pointer.mp4",
  "capturedAt": "2026-08-28T03:14:22+08:00",
  "notes": "Trail persists across several frames after pointer motion."
}
```

Allowed `sourceType` values include `runtime-behavior`, `network-request`, `dom-snapshot`, `source-code`, `asset-inspection`, and `visual-capture`. Evidence must be locatable inside the case or by a public URL without credentials.

## Claim record

```json
{
  "id": "CLAIM-7",
  "claim": "The hero trail uses a frame-feedback render target.",
  "confidence": "inferred",
  "evidenceIds": ["EV-12"],
  "limits": "The framebuffer implementation was not source-confirmed."
}
```

Every `observed` or `source-confirmed` claim needs at least one evidence ID. Never store cookies, headers, tokens, session storage, or authenticated content.
