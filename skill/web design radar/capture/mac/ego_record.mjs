// Web Design Radar — mac-ego recording backend.
// Run on the Mac:  ego-browser nodejs < ego_record.mjs   (reads ~/web-design-radar-mac/targets.json; ego-browser does not forward env vars)
// targets.json: {"url": "...", "runName": "...", "outDir": "~/web-design-radar-mac/out", "seconds": 8, "consent": "hide"|"click",
//                "sections": [{"order":1,"startY":0,"endY":450}, ...]}
// Uses ONE agent-owned TaskSpace (never the user's tabs), public pages only, finish({keep: []}) at the end.
const fs = await import("node:fs/promises");
const path = await import("node:path");
const { execFileSync } = await import("node:child_process");
const HOME = (await import("node:os")).homedir();
const cfg = JSON.parse(await fs.readFile(process.env.WDR_CONFIG || path.join(HOME, "web-design-radar-mac", "targets.json"), "utf8"));
const OUT_ROOT = (cfg.outDir || "~/web-design-radar-mac/out").replace(/^~(?=\/|$)/, HOME);
const OUT = path.join(OUT_ROOT, cfg.runName);
const SECONDS = Math.min(Math.max(cfg.seconds || 8, 6.5), 11.5);
const FFMPEG = cfg.ffmpeg || "/opt/homebrew/bin/ffmpeg";
const FFPROBE = FFMPEG.replace(/ffmpeg$/, "ffprobe");
await fs.mkdir(path.join(OUT, "recordings"), { recursive: true });
await fs.mkdir(path.join(OUT, "screenshots"), { recursive: true });
const T = (p, ms, what) => Promise.race([p, new Promise((_, r) => setTimeout(() => r(new Error("timeout " + what)), ms))]);
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const summary = { url: cfg.url, browserUsed: "ego-lite", captureMethod: "ego-lite-cdp-screencast", startedAt: new Date().toISOString(),
                  viewport: "1440x900", consent: null, sections: [], errors: [] };

// consent logic ported from capture/capture_lib.py (accept-type labels in a cookie/privacy context; never login/subscribe)
const CONSENT = {
  accept: ["accept all","accept all cookies","accept cookies","accept","allow all","allow all cookies","allow cookies","allow","agree","i agree",
    "agree and close","got it","ok","okay","i understand","understood","continue","confirm","yes","accepter","tout accepter","j'accepte",
    "accepter et fermer","d'accord","akzeptieren","alle akzeptieren","zustimmen","einverstanden","verstanden","aceptar","aceptar todo","acepto",
    "de acuerdo","aceitar","aceitar todos","concordo","accetta","accetta tutto","accetto","accetta tutti","accepteren","alles accepteren","akkoord",
    "godkänn","acceptera","godta","accepter alle","hyväksy","zaakceptuj","akceptuję","souhlasím","elfogadom","принять","согласен","kabul et",
    "同意","接受","全部接受","接受全部","我同意","同意并继续","好的","知道了","允许","すべて同意","同意する","受け入れる","모두 동의","동의","수락"],
  forbidden: "log ?in|sign ?in|sign ?up|register|subscribe|subscription|newsletter|create account|password|buy|checkout|登录|登入|注册|订阅|购买|abonn|s'inscrire|anmelden|registrieren|suscrib|iscriv",
  context: "cookie|consent|gdpr|ccpa|privacy|tracking|personal data|datenschutz|confidentialit|privacidad|riservatezza|隐私|隱私|个人信息|クッキー|쿠키|rgpd|traceurs",
  known: ["#onetrust-accept-btn-handler","#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll","#CybotCookiebotDialogBodyButtonAccept",
    "#didomi-notice-agree-button","[data-testid='uc-accept-all-button']",".qc-cmp2-summary-buttons button[mode='primary']","#truste-consent-button",
    ".iubenda-cs-accept-btn",".cmplz-accept",".cky-btn-accept",".osano-cm-accept-all","[fs-cc='allow']","#axeptio_btn_acceptAll"],
  hideCss: "#onetrust-consent-sdk,#CybotCookiebotDialog,#didomi-host,#usercentrics-root,.qc-cmp2-container,.iubenda-cs-container,.cmplz-cookiebanner,.cky-consent-container,.osano-cm-window,[fs-cc='banner'],.cookie-banner,.cookie-consent,#cookie-banner,#cookie-consent,[class*='cookie-banner'],[id*='cookie-banner']{display:none!important}",
};
const consentInPage = (c) => {
  const forb = new RegExp(c.forbidden, "i"), ctxRe = new RegExp(c.context, "i");
  const norm = (t) => (t || "").replace(/[\s\u00a0]+/g, " ").trim().toLowerCase().replace(/^[ .!→>✓×]+|[ .!→>✓×]+$/g, "");
  const isAccept = (t) => { const l = norm(t); if (!l || l.length > 40 || forb.test(l)) return false;
    return c.accept.includes(l) || c.accept.some((w) => w.length > 3 && l.startsWith(w + " ") && l.length <= w.length + 14); };
  const vis = (el) => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const out = { clicked: [], hidden: [] };
  if (c.mode === "click") {
    for (const sel of c.known) { const el = document.querySelector(sel); if (el && vis(el) && !forb.test(el.innerText || "")) { el.click(); out.clicked.push(sel); break; } }
    if (!out.clicked.length) for (const el of document.querySelectorAll("button,a,[role=button],input[type=button],input[type=submit]")) {
      if (!vis(el)) continue; const label = el.innerText || el.value || el.getAttribute("aria-label") || ""; if (!isAccept(label)) continue;
      let ctx = ""; for (let e = el, i = 0; e && i < 6; e = e.parentElement, i++) { ctx = (e.innerText || "").slice(0, 600); if (ctx.length > 60) break; }
      if (ctxRe.test(ctx)) { el.click(); out.clicked.push(norm(label)); break; } }
  }
  const st = document.createElement("style"); st.textContent = c.hideCss; document.head.appendChild(st);
  for (const el of document.querySelectorAll("body *")) { const s = getComputedStyle(el); if (s.position !== "fixed" && s.position !== "sticky") continue;
    const r = el.getBoundingClientRect(); if (r.width * r.height < 4000) continue; const t = (el.innerText || "").slice(0, 800);
    if (!ctxRe.test(t) && !ctxRe.test(el.id + " " + el.className)) continue;
    if (r.height > innerHeight * 0.95 && r.width > innerWidth * 0.95 && !/cookie|consent/i.test(t)) continue;
    el.style.setProperty("display", "none", "important"); out.hidden.push((el.tagName + (el.id ? "#" + el.id : "") + "." + String(el.className).split(" ").join(".")).slice(0, 100)); }
  return out;
};

const task = await T(taskSpace(`wdr record ${cfg.runName}`), 30000, "taskSpace");
log("taskSpace", task.spaceId);
const page = task.page("p1");
try {
  await page.cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await T(page.goto(cfg.url, { waitUntil: "load", timeout: 45000 }), 50000, "goto");
  try { await page.waitForLoadState("networkidle", { timeout: 10000 }); } catch {}
  await page.waitForTimeout(2500);
  summary.consent = await page.evaluate(consentInPage, { ...CONSENT, mode: cfg.consent || "hide" });
  await page.waitForTimeout(500);
  summary.consent.after = await page.evaluate(consentInPage, { ...CONSENT, mode: "hide" });
  summary.page = await page.evaluate(() => ({ title: document.title, docHeight: document.documentElement.scrollHeight, innerWidth, innerHeight,
    dpr: devicePixelRatio, renderer: (() => { try { const g = document.createElement("canvas").getContext("webgl2"); const d = g.getExtension("WEBGL_debug_renderer_info"); return g.getParameter(d.UNMASKED_RENDERER_WEBGL); } catch (e) { return String(e); } })() }));
  log("page", JSON.stringify(summary.page), "consent", JSON.stringify(summary.consent).slice(0, 200));
  await page.evaluate(() => { window.__wdrFrames = 0; const f = () => { window.__wdrFrames++; requestAnimationFrame(f); }; requestAnimationFrame(f); });

  for (const s of cfg.sections) {
    const n = String(s.order).padStart(2, "0");
    const frameDir = await fs.mkdtemp(path.join(OUT, `.frames-${n}-`));
    await page.evaluate((y) => window.scrollTo(0, y), s.startY);
    await page.mouse.move(288, 450);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(OUT, "screenshots", `${n}-desktop-start.png`) });
    await page.events(); // drop old buffered events
    await page.cdp("Page.startScreencast", { format: "jpeg", quality: 80, maxWidth: 1440, maxHeight: 900, everyNthFrame: 1 });
    const f0 = await page.evaluate(() => window.__wdrFrames);
    const t0 = Date.now();
    // in-page real-time easeInOut scroll (no per-step round trips)
    await page.evaluate(([a, b, ms]) => { const t0 = performance.now(); const ease = (p) => p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      window.__wdrScrollDone = false;
      const f = (now) => { const p = Math.min((now - t0) / ms, 1); const y = a + (b - a) * ease(p); window.scrollTo(0, y);
        if (window.lenis && window.lenis.scrollTo) { try { window.lenis.scrollTo(y, { immediate: true }); } catch (e) {} }
        if (p < 1) requestAnimationFrame(f); else window.__wdrScrollDone = true; };
      requestAnimationFrame(f); }, [s.startY, s.endY, Math.round(SECONDS * 1000)]);
    const frames = []; let lastMouse = 0;
    while (Date.now() - t0 < SECONDS * 1000 + 300) {
      const ev = await page.events();
      for (const e of ev) {
        if (e.method !== "Page.screencastFrame") continue;
        const ts = e.params.metadata.timestamp;
        const file = path.join(frameDir, `f-${String(frames.length).padStart(5, "0")}.jpg`);
        await fs.writeFile(file, Buffer.from(e.params.data, "base64"));
        frames.push({ file, ts });
        page.cdp("Page.screencastFrameAck", { sessionId: e.params.sessionId }).catch(() => {});
      }
      const el = Date.now() - t0;
      if (el - lastMouse > 120) { lastMouse = el; const p = Math.min(el / (SECONDS * 1000), 1);
        page.mouse.move(Math.round(1440 * (0.2 + 0.6 * p)), Math.round(900 * (0.5 + 0.25 * Math.sin(p * 6.28)))).catch(() => {}); }
      await new Promise((r) => setTimeout(r, 4));
    }
    await page.cdp("Page.stopScreencast");
    const wall = (Date.now() - t0) / 1000;
    const f1 = await page.evaluate(() => window.__wdrFrames);
    await page.screenshot({ path: path.join(OUT, "screenshots", `${n}-desktop-end.png`) });
    // real-time concat list from frame timestamps
    const lines = [];
    for (let i = 0; i < frames.length; i++) {
      const d = i + 1 < frames.length ? frames[i + 1].ts - frames[i].ts : 1 / 30;
      lines.push(`file '${frames[i].file}'`, `duration ${Math.max(d, 0.001).toFixed(4)}`);
    }
    if (frames.length) lines.push(`file '${frames[frames.length - 1].file}'`);
    const list = path.join(frameDir, "list.txt"); await fs.writeFile(list, lines.join("\n") + "\n");
    const out = path.join(OUT, "recordings", `${n}-desktop-scroll.mp4`);
    const rec = { order: s.order, startY: s.startY, endY: s.endY, frames: frames.length, wallSeconds: +wall.toFixed(2),
                  pageFps: +((f1 - f0) / wall).toFixed(1), path: `recordings/${n}-desktop-scroll.mp4` };
    try {
      execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-fps_mode", "vfr",
        "-vf", "scale=1440:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]);
      const dur = parseFloat(execFileSync(FFPROBE, ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out]).toString());
      const span = frames.length > 1 ? frames[frames.length - 1].ts - frames[0].ts : 0;
      Object.assign(rec, { durationSeconds: +dur.toFixed(3), effectiveFps: span ? +((frames.length - 1) / span).toFixed(1) : 0 });
    } catch (e) { rec.error = String(e).slice(0, 300); summary.errors.push(rec.error); }
    await fs.rm(frameDir, { recursive: true, force: true });
    summary.sections.push(rec);
    log("section", JSON.stringify(rec));
  }
  await page.cdp("Emulation.clearDeviceMetricsOverride");
} catch (e) { summary.errors.push(String(e).slice(0, 400)); log("ERR", String(e).slice(0, 400)); }
summary.finishedAt = new Date().toISOString();
summary.taskSpaceId = task.spaceId;
summary.finish = await T(task.finish({ keep: [] }), 20000, "finish").catch((e) => String(e));
await fs.writeFile(path.join(OUT, "mac-record-summary.json"), JSON.stringify(summary, null, 2));
log("DONE", OUT, JSON.stringify(summary.finish));
process.exit(0);
