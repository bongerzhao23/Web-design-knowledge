# Public Asset Policy

Archive only files requested while visiting a public target page or explicitly referenced by public source and necessary for local replication.

## Allowed records

For every model, buffer, texture, shader, video, image, font, or relevant bundle, record:

- redacted original URL and MIME type;
- local path, byte size, SHA-256, `usedBy`, and status;
- access source (`public-page-request`), license (`unknown` when not stated), and failure reason;
- Draco, Meshopt, KTX2/Basis, external buffer, and texture relationships for GLTF assets;
- font family/weight/style/format and CSS mapping.

Use `record-asset`; it enforces a 250 MiB per-file and 1 GiB per-revision limit. Oversized, expired signed-URL, CORS-blocked, or unavailable assets remain metadata-only rather than disappearing from the manifest. Sensitive URL keys are redacted. Never store request headers or credentials.

Do not bypass authentication, CAPTCHA, DRM, paywalls, access checks, or obfuscation. Do not copy a whole minified bundle merely to claim ownership of a small shader; preserve the smallest relevant public fragment with context. `license: unknown` requires the replica prompt to replace the asset or obtain permission before production use.
