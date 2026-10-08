#!/usr/bin/env python3
"""Standalone headless capture for Web Design Radar (v2, asyncio).

Kit-owned Playwright Chromium only; fresh cookie-less contexts; public pages only. Consent banners are
dismissed (accept-type buttons only, never login/subscribe) or hidden with CSS, and logged.

Outputs into --staging (the run's stagingDir):
  screenshots/_global/*.png, screenshots/_global/steps/*, screenshots/_global/lifecycle/*,
  screenshots/NN-sec/{desktop-01..04,mobile-01}.png, recordings/NN-desktop-scroll.mp4,
  evidence/capture-summary.json, evidence/section-index.draft.json, evidence/EV-CAP-*.json
Raw HTML/CSS + asset cache go OUTSIDE staging: <staging>/../raw-analysis/
"""
from __future__ import annotations

import argparse, asyncio, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(KIT / ".browsers"))
from playwright.async_api import async_playwright  # noqa: E402
import capture_lib as L  # noqa: E402

DESKTOP = (1440, 900)
MOBILE = (390, 844)
CHROME_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
               "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"]
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
             "Version/17.0 Mobile/15E148 Safari/604.1")

LIB_SCRIPT_PATTERNS = {
    "GSAP": r"gsap|greensock|TweenMax", "ScrollTrigger": r"ScrollTrigger", "Three.js": r"three(\.module)?(\.min)?\.js|/three@|three\.core",
    "Lenis": r"lenis", "Locomotive Scroll": r"locomotive", "Barba.js": r"barba", "Swiper": r"swiper", "PixiJS": r"pixi",
    "Babylon.js": r"babylon", "OGL": r"/ogl", "Spline": r"spline", "Rive": r"rive\.", "Lottie": r"lottie|bodymovin",
    "Webflow": r"webflow", "Framer": r"framer", "Next.js": r"/_next/", "Nuxt": r"/_nuxt/", "Draco decoder": r"draco",
    "Basis/KTX2 transcoder": r"basis_transcoder|ktx2",
}
GLOBALS_JS = r"""
() => { const w = window, out = {};
  const probe = {
    'GSAP': () => w.gsap && (w.gsap.version || true), 'ScrollTrigger': () => w.ScrollTrigger && true,
    'Three.js': () => w.THREE && (w.THREE.REVISION || true), 'Three.js (__THREE__)': () => w.__THREE__ || null,
    'Lenis': () => (w.Lenis || w.lenis) && true, 'Locomotive Scroll': () => w.LocomotiveScroll && true,
    'Barba.js': () => w.barba && true, 'Swiper': () => w.Swiper && true, 'PixiJS': () => w.PIXI && (w.PIXI.VERSION || true),
    'Babylon.js': () => w.BABYLON && true, 'anime.js': () => w.anime && true, 'p5.js': () => w.p5 && true,
    'Lottie': () => (w.lottie || w.bodymovin) && true, 'jQuery': () => w.jQuery && (w.jQuery.fn && w.jQuery.fn.jquery),
    'Next.js': () => w.__NEXT_DATA__ && true, 'Nuxt': () => (w.__NUXT__ || w.$nuxt) && true, 'Vue': () => (w.Vue || w.__VUE__) && true,
    'React': () => !!document.querySelector('[data-reactroot]') || null, 'Webflow': () => w.Webflow && true,
    'Framer': () => !!document.querySelector('[data-framer-name]') || null };
  for (const [k, f] of Object.entries(probe)) { try { const v = f(); if (v) out[k] = v; } catch (e) {} }
  return {globals: out, title: document.title, lang: document.documentElement.lang,
          docHeight: document.documentElement.scrollHeight, dpr: w.devicePixelRatio,
          fonts: [...new Set([...document.fonts].map(f => `${f.family} ${f.weight} ${f.style} ${f.status}`))].slice(0, 40),
          scripts: [...document.scripts].map(s => s.src).filter(Boolean)}; }
"""
CANVAS_JS = r"""
() => [...document.querySelectorAll('canvas')].map(c => { const r = c.getBoundingClientRect(), cs = getComputedStyle(c);
  return {w: c.width, h: c.height, cssW: Math.round(r.width), cssH: Math.round(r.height), position: cs.position,
          zIndex: cs.zIndex, display: cs.display, visible: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden',
          cls: c.className && String(c.className).slice(0, 80), id: c.id}; })
"""
WEBGL_JS = r"""
() => { const c = document.createElement('canvas'); const r = {};
  for (const k of ['webgl2','webgl']) { try { const g = c.getContext(k); if (g) { r[k] = true;
    const d = g.getExtension('WEBGL_debug_renderer_info'); if (d) r.renderer = g.getParameter(d.UNMASKED_RENDERER_WEBGL); } } catch(e){} }
  r.webgpu = !!navigator.gpu; return r; }
"""
CANDIDATES_JS = r"""
(vw) => { const out = [], seen = new Set();
  const bgOf = (el) => { for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const b = getComputedStyle(e).backgroundColor; if (b && b !== 'rgba(0, 0, 0, 0)' && b !== 'transparent') return b; } return 'none'; };
  const sel = (el) => { if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1) return '#' + CSS.escape(el.id);
      const parts = []; for (let e = el; e && e !== document.body; e = e.parentElement) {
        let i = 1, s = e; while ((s = s.previousElementSibling)) if (s.tagName === e.tagName) i++;
        parts.unshift(e.tagName.toLowerCase() + ':nth-of-type(' + i + ')'); } return 'body > ' + parts.join(' > '); };
  const walk = (el, depth) => { if (depth > 6) return;
    for (const c of el.children) { const cs = getComputedStyle(c);
      if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
      const r = c.getBoundingClientRect(); if (r.height < 40) continue;
      const tag = c.tagName.toLowerCase();
      if (['script','style','link','noscript','svg','canvas','video','img'].includes(tag)) continue;
      const s = sel(c); if (!seen.has(s)) { seen.add(s);
        out.push({selector: s, top: Math.round(r.top + scrollY), height: Math.round(r.height), width_ratio: r.width / vw,
          semantic: ['section','header','footer','article','aside','nav'].includes(tag), depth, bg: bgOf(c), tag,
          id: c.id || '', cls: (c.className && String(c.className).slice(0, 80)) || '',
          text: (c.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160)}); }
      walk(c, depth + 1); } };
  walk(document.body, 0); return {docH: document.documentElement.scrollHeight, candidates: out}; }
"""
LOCATE_JS = r"""
(s) => { const el = document.querySelector(s); if (!el) return null; const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect(); return {top: Math.round(r.top + scrollY), height: Math.round(r.height),
  visible: cs.display !== 'none' && cs.visibility !== 'hidden' && r.height > 0}; }
"""
CONSENT_GENERIC_JS = r"""
() => { const vis = el => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  document.querySelectorAll('[data-wdr-cand]').forEach(e => e.removeAttribute('data-wdr-cand'));
  const res = []; let k = 0; const els = document.querySelectorAll('button, a, [role=button], input[type=button], input[type=submit], div[tabindex], span[tabindex]');
  for (const el of els) { if (!vis(el)) continue; const label = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
    if (!label || label.length > 40) continue;
    let ctx = ''; for (let e = el, i = 0; e && i < 6; e = e.parentElement, i++) { ctx = (e.innerText || '').slice(0, 600); if (ctx.length > 60) break; }
    el.setAttribute('data-wdr-cand', String(k)); res.push({label, ctx, k: k++}); }
  return res; }
"""
CONSENT_OVERLAY_JS = r"""
(rx) => { const re = new RegExp(rx, 'i'); const hidden = [];
  for (const el of document.querySelectorAll('body *')) { const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    const r = el.getBoundingClientRect(); if (r.width * r.height < 4000) continue;
    const t = (el.innerText || '').slice(0, 800); if (!re.test(t) && !re.test(el.id + ' ' + el.className)) continue;
    if (r.height > innerHeight * 0.95 && r.width > innerWidth * 0.95 && !/cookie|consent/i.test(t)) continue;
    el.style.setProperty('display', 'none', 'important');
    hidden.push((el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + String(el.className).split(' ').join('.') : '')).slice(0, 120)); }
  return hidden; }
"""
FPS_PROBE_JS = r"""
() => { window.__wdrFrames = 0; const f = () => { window.__wdrFrames++; requestAnimationFrame(f); }; requestAnimationFrame(f); }
"""


class Cap:
    def __init__(self, a):
        self.a = a
        self.root = Path(a.staging).resolve()
        self.raw = self.root.parent / "raw-analysis"
        self.cache = self.raw / "asset-cache"
        for d in ("screenshots/_global/steps", "screenshots/_global/lifecycle", "recordings", "evidence"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self.raw.mkdir(exist_ok=True)
        self.console, self.page_errors, self.failed, self.network, self.assets, self.shots = [], [], [], {}, {}, []
        self.consent, self.timings, self.lifecycle = [], {}, []
        self.sections_ready: asyncio.Future = None
        self.t0 = time.time()

    def mark(self, k):
        self.timings[k] = round(time.time() - self.t0, 1)

    # ---------- page plumbing ----------
    def attach(self, page, label):
        def on_console(m):
            if m.type in ("error", "warning"):
                self.console.append({"viewport": label, "type": m.type, "text": m.text[:400], "t": round(time.time() - self.t0, 1)})
        page.on("console", on_console)
        page.on("pageerror", lambda e: self.page_errors.append({"viewport": label, "error": str(e)[:400], "t": round(time.time() - self.t0, 1)}))
        page.on("requestfailed", lambda r: self.failed.append({"viewport": label, "url": L.redact(r.url)[:400], "rawUrl": r.url,
                                                               "failure": (r.failure or "")[:200], "type": r.resource_type}))

        async def on_resp(resp):
            try:
                url = resp.url
                if url.startswith("data:"):
                    return
                h = resp.headers
                ct = h.get("content-type", "")
                size = int(h["content-length"]) if h.get("content-length", "").isdigit() else None
                kind = L.classify(url, ct, resp.request.resource_type)
                self.network[url] = {"type": resp.request.resource_type, "status": resp.status, "contentType": ct}
                if resp.status >= 400:
                    self.failed.append({"viewport": label, "url": L.redact(url)[:400], "rawUrl": url, "failure": f"HTTP {resp.status}", "type": resp.request.resource_type})
                if not kind or url in self.assets:
                    return
                rec = {"url": L.redact(url), "rawUrl": url, "kind": kind, "contentType": ct, "status": resp.status, "bytes": size,
                       "cachedFile": None, "firstSeen": label}
                self.assets[url] = rec
                if kind in ("model", "shader", "font", "texture") and resp.status == 200 and (size is None or size <= 25 * 2**20):
                    body = await resp.body()
                    rec["bytes"] = len(body)
                    if self.a.cache_assets:
                        self.cache.mkdir(parents=True, exist_ok=True)
                        name = hashlib.sha256(url.encode()).hexdigest()[:12] + "-" + (Path(urlsplit(url).path).name or "asset")[:60]
                        (self.cache / name).write_bytes(body)
                        rec["cachedFile"] = str(self.cache / name)
            except Exception:
                pass
        page.on("response", lambda r: asyncio.ensure_future(on_resp(r)))

    async def load(self, page, label):
        await page.goto(self.a.url, wait_until="domcontentloaded", timeout=self.a.timeout)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000 if self.a.fast else 15000)
        except Exception:
            pass
        await page.wait_for_timeout(1500 if self.a.fast else 2500)
        await self.dismiss_consent(page, label)

    async def dismiss_consent(self, page, label):
        log = {"viewport": label, "clicked": [], "hiddenByCss": [], "frames": len(page.frames)}
        for attempt in range(2):
            done = False
            for frame in page.frames:
                for cmp_name, selector in L.KNOWN_CMP_SELECTORS:
                    try:
                        loc = frame.locator(selector).first
                        if await loc.count() and await loc.is_visible():
                            txt = (await loc.inner_text(timeout=1000)).strip()[:40]
                            if L.is_forbidden_label(txt):
                                continue
                            await loc.click(timeout=2000)
                            log["clicked"].append({"cmp": cmp_name, "selector": selector, "label": txt, "frame": frame.url[:120]})
                            done = True
                            break
                    except Exception:
                        continue
                if done:
                    break
                try:
                    items = await frame.evaluate(CONSENT_GENERIC_JS)
                except Exception:
                    continue
                for it in items:
                    in_cmp_frame = frame != page.main_frame and L.is_consent_context(frame.url)
                    if L.is_accept_label(it["label"]) and (L.is_consent_context(it["ctx"]) or in_cmp_frame):
                        try:
                            loc = frame.locator(f"[data-wdr-cand='{it['k']}']").first
                            await loc.click(timeout=2000)
                            log["clicked"].append({"cmp": "generic", "label": it["label"], "frame": frame.url[:120]})
                            done = True
                            break
                        except Exception:
                            continue
                if done:
                    break
            if not done:
                break
            await page.wait_for_timeout(600)
        try:
            await page.add_style_tag(content=L.CONSENT_HIDE_CSS)
            log["hiddenByCss"] = await page.evaluate(CONSENT_OVERLAY_JS, L.CONSENT_CONTEXT.pattern)
        except Exception as e:
            log["cssError"] = str(e)[:200]
        self.consent.append(log)

    async def shot(self, page, path: Path, viewport, state, trigger, full_page=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(path), full_page=full_page, timeout=60000)
        rec = {"path": path.relative_to(self.root).as_posix(), "viewport": viewport, "state": state, "trigger": trigger,
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "scrollY": await page.evaluate("scrollY")}
        self.shots.append(rec)
        return rec

    @staticmethod
    async def jump(page, target, settle=350):
        """Screenshot positioning: instant scroll + one small real wheel nudge so scroll-driven libs update."""
        await page.evaluate("(y) => { window.scrollTo(0, y); if (window.lenis && window.lenis.scrollTo) { try { window.lenis.scrollTo(y, {immediate: true}); } catch(e){} } }", target)
        await page.mouse.wheel(0, 1)
        await page.wait_for_timeout(settle)

    @staticmethod
    async def realtime_scroll(page, start, end, seconds, mouse=None):
        """Recording: in-page rAF-driven scroll over real wall time (no per-step round trips), easeInOut;
        pointer path is driven concurrently from Python every ~100 ms."""
        js = """([a, b, ms]) => new Promise(res => { const t0 = performance.now();
            const ease = p => p < .5 ? 2*p*p : 1 - Math.pow(-2*p + 2, 2) / 2;
            const f = now => { const p = Math.min((now - t0) / ms, 1); const y = a + (b - a) * ease(p);
              window.scrollTo(0, y); if (window.lenis && window.lenis.scrollTo) { try { window.lenis.scrollTo(y, {immediate: true}); } catch(e){} }
              if (p < 1) requestAnimationFrame(f); else res(); }; requestAnimationFrame(f); })"""
        task = asyncio.ensure_future(page.evaluate(js, [start, end, int(seconds * 1000)]))
        t0 = time.time()
        while not task.done() and mouse:
            p = min((time.time() - t0) / seconds, 1)
            try:
                await page.mouse.move(*mouse(p))
            except Exception:
                pass
            await asyncio.sleep(0.1)
        await task

    @staticmethod
    async def smooth_scroll(page, target, seconds=0.8, mouse=None):
        cur = await page.evaluate("scrollY")
        steps = max(int(seconds * 60), 1)
        delta = (target - cur) / steps
        t_start = time.time()
        for i in range(steps):
            await page.mouse.wheel(0, delta)
            if mouse:
                p = (i + 1) / steps
                await page.mouse.move(*mouse(p))
            wait = t_start + (i + 1) * seconds / steps - time.time()
            if wait > 0:
                await asyncio.sleep(wait)
        await page.wait_for_timeout(250)
        if abs(await page.evaluate("scrollY") - target) > 120:
            await page.evaluate("(y) => window.scrollTo(0, y)", target)
            await page.wait_for_timeout(200)

    # ---------- tasks ----------
    async def desktop(self, browser):
        a = self.a
        ctx = await browser.new_context(viewport={"width": DESKTOP[0], "height": DESKTOP[1]}, device_scale_factor=1)
        page = await ctx.new_page()
        self.attach(page, "desktop")
        t = time.time()
        await self.load(page, "desktop")
        self.summary_load = round(time.time() - t, 1)
        self.final_url = page.url
        g = self.root / "screenshots" / "_global"
        await self.shot(page, g / "desktop-01-after-load.png", "1440x900", "after-load", "goto + networkidle + consent dismissed")
        self.info = await page.evaluate(GLOBALS_JS)
        self.webgl = await page.evaluate(WEBGL_JS)
        self.wall = bool(re.search(r"captcha|verify you are human|sign in to continue|subscribe to continue|access denied",
                                   await page.evaluate("document.body ? document.body.innerText.slice(0,3000) : ''"), re.I))
        vh = DESKTOP[1]
        doc_h = await page.evaluate("document.documentElement.scrollHeight")
        stride = 3 if a.fast else 1
        for i in range(0, min(int(doc_h / vh) + 1, 12), stride):
            await self.jump(page, i * vh)
            await self.shot(page, g / "steps" / f"desktop-step-{i:02d}.png", "1440x900", f"scroll-step-{i}", f"scrollTo + wheel nudge to y={i*vh}")
        await self.jump(page, 0)
        cand = await page.evaluate(CANDIDATES_JS, DESKTOP[0])
        self.doc_h = cand["docH"]
        secs = L.choose_sections(cand["candidates"], cand["docH"], vh, a.max_sections)
        self.detection = {"method": "dom-full-width-blocks" if secs and secs[0].get("selector") else "viewport-slices",
                          "candidates": len(cand["candidates"]), "count": len(secs), "docHeight": cand["docH"]}
        self.sections = secs
        self.sections_ready.set_result(secs)
        self.mark("desktopSectionsDetected")
        for s in secs:
            n = s["order"]
            d = self.root / "screenshots" / f"{n:02d}-sec"
            top, h = max(s["top"], 0), s["height"]
            caps = []
            y = max(top - int(vh * 0.6), 0)
            await self.jump(page, y)
            caps.append(await self.shot(page, d / "desktop-01-enter.png", "1440x900", "entering", f"scrollTo + wheel nudge to y={y} (section top at 60% vh)"))
            await self.jump(page, top)
            await page.mouse.move(DESKTOP[0] // 2, DESKTOP[1] // 2)
            await page.wait_for_timeout(400)
            caps.append(await self.shot(page, d / "desktop-02-rest.png", "1440x900", "rest-aligned", f"scrollTo + wheel nudge to section top y={top}, pointer center"))
            await page.mouse.move(int(DESKTOP[0] * 0.8), int(DESKTOP[1] * 0.3), steps=15)
            await page.wait_for_timeout(400)
            caps.append(await self.shot(page, d / "desktop-03-pointer.png", "1440x900", "pointer-moved", "pointer center -> (80%,30%) in 15 steps"))
            mid = top + max(h - vh, 0) // 2 + int(vh * 0.5)
            await self.jump(page, mid)
            caps.append(await self.shot(page, d / "desktop-04-scroll-through.png", "1440x900", "scroll-through", f"scrollTo + wheel nudge to y={mid}"))
            s["captures"] = caps
        self.mark("desktopShotsDone")
        (self.raw / "desktop.html").write_text(await page.content(), encoding="utf-8")
        css = await page.evaluate("""() => [...document.styleSheets].map(s => { try { return `/* ${s.href||'inline'} */\\n` +
            [...s.cssRules].map(r => r.cssText).join('\\n'); } catch(e) { return `/* ${s.href} (cross-origin) */`; } }).join('\\n\\n')""")
        (self.raw / "desktop.css").write_text(css, encoding="utf-8")
        await self.lifecycle_checks(page)
        await ctx.close()

    async def lifecycle_checks(self, page):
        lc = self.root / "screenshots" / "_global" / "lifecycle"

        async def state(step, shot_name, method):
            n_err = len(self.page_errors) + len([c for c in self.console if c["type"] == "error"])
            rec = {"step": step, "method": method, "canvases": await page.evaluate(CANVAS_JS),
                   "visibility": await page.evaluate("document.visibilityState"),
                   "viewport": await page.evaluate("[innerWidth, innerHeight]"),
                   "errorsSoFar": n_err}
            if shot_name:
                rec["screenshot"] = (await self.shot(page, lc / shot_name, f"{rec['viewport'][0]}x{rec['viewport'][1]}", step, method))["path"]
            self.lifecycle.append(rec)
        await self.jump(page, 0)
        await state("baseline", "desktop-lifecycle-0-baseline.png", "top of page before checks")
        await page.set_viewport_size({"width": MOBILE[0], "height": MOBILE[1]})
        await page.wait_for_timeout(1200)
        await state("resize-to-mobile", "mobile-lifecycle-1-resized.png", "set_viewport_size 1440x900 -> 390x844, wait 1.2s")
        await page.set_viewport_size({"width": DESKTOP[0], "height": DESKTOP[1]})
        await page.wait_for_timeout(1200)
        await state("resize-back-to-desktop", "desktop-lifecycle-2-resized-back.png", "set_viewport_size 390x844 -> 1440x900, wait 1.2s")
        other = await page.context.new_page()
        await other.bring_to_front()
        await page.wait_for_timeout(300)
        method = "bring_to_front(other tab)"
        if await page.evaluate("document.visibilityState") == "visible":
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Page.setWebLifecycleState", {"state": "frozen"})
            await asyncio.sleep(1.0)
            await cdp.send("Page.setWebLifecycleState", {"state": "active"})
            method = "CDP Page.setWebLifecycleState frozen -> active (headless keeps tabs visible)"
        else:
            await state("hidden", None, method)
            await asyncio.sleep(1.0)
        await page.bring_to_front()
        await other.close()
        await page.wait_for_timeout(800)
        await state("returned-visible", "desktop-lifecycle-3-returned.png", method)
        await page.reload(wait_until="domcontentloaded", timeout=self.a.timeout)
        await page.wait_for_timeout(4000)
        try:
            await page.add_style_tag(content=L.CONSENT_HIDE_CSS)
        except Exception:
            pass
        await state("reloaded", "desktop-lifecycle-4-reloaded.png", "page.reload + 4s")

    async def mobile(self, browser):
        ctx = await browser.new_context(viewport={"width": MOBILE[0], "height": MOBILE[1]}, device_scale_factor=2,
                                        is_mobile=True, has_touch=True, user_agent=MOBILE_UA)
        page = await ctx.new_page()
        self.attach(page, "mobile")
        await self.load(page, "mobile")
        g = self.root / "screenshots" / "_global"
        await self.shot(page, g / "mobile-01-after-load.png", "390x844", "after-load", "goto + networkidle + consent dismissed")
        mdoc = await page.evaluate("document.documentElement.scrollHeight")
        self.mobile_doc_h = mdoc
        stride = 3 if self.a.fast else 1
        for i in range(0, min(int(mdoc / MOBILE[1]) + 1, 12), stride):
            await page.evaluate("(y) => window.scrollTo(0, y)", i * MOBILE[1])
            await page.wait_for_timeout(450)
            await self.shot(page, g / "steps" / f"mobile-step-{i:02d}.png", "390x844", f"scroll-step-{i}", f"scrollTo y={i*MOBILE[1]}")
        secs = await self.sections_ready
        for s in secs:
            loc = await page.evaluate(LOCATE_JS, s["selector"]) if s.get("selector") else None
            if loc and loc["visible"]:
                y, how = max(loc["top"], 0), f"same DOM element {s['selector']} at mobile y={loc['top']}"
                s["mobile"] = {"matched": True, "top": loc["top"], "height": loc["height"]}
            else:
                y = int(s["top"] * mdoc / max(self.doc_h, 1))
                how = f"element not visible on mobile; ratio fallback y={y}"
                s["mobile"] = {"matched": False, "top": y}
            await page.evaluate("(y) => window.scrollTo(0, y)", y)
            await page.wait_for_timeout(700)
            s["mobileCapture"] = await self.shot(page, self.root / "screenshots" / f"{s['order']:02d}-sec" / "mobile-01-representative.png",
                                                 "390x844", "mobile-representative", how)
        (self.raw / "mobile.html").write_text(await page.content(), encoding="utf-8")
        self.mark("mobileDone")
        await ctx.close()

    async def recorder(self, browser):
        if self.a.no_video:
            return
        a = self.a
        size = {"width": a.record_width, "height": int(a.record_width * DESKTOP[1] / DESKTOP[0])}
        vid_dir = Path(tempfile.mkdtemp(prefix="wdr-video-"))
        ctx = await browser.new_context(viewport={"width": DESKTOP[0], "height": DESKTOP[1]}, device_scale_factor=1,
                                        record_video_dir=str(vid_dir), record_video_size=size)
        page = await ctx.new_page()
        t_open = time.time()
        self.attach(page, "recording")
        await self.load(page, "recording")
        secs = await self.sections_ready
        await page.evaluate(FPS_PROBE_JS)
        vh = DESKTOP[1]
        segs = []
        for s in secs:
            top, h = max(s["top"], 0), s["height"]
            start_y, end_y = max(top - int(vh * 0.3), 0), top + max(h - vh, 0) + int(vh * 0.5)
            await page.evaluate("(y) => window.scrollTo(0, y)", start_y)
            await page.wait_for_timeout(500)
            f0 = await page.evaluate("window.__wdrFrames")
            t_s = time.time() - t_open
            secs_len = a.video_seconds
            mouse = lambda p: (int(DESKTOP[0] * (0.2 + 0.6 * p)), int(DESKTOP[1] * (0.5 + 0.25 * math.sin(p * 6.28))))
            await self.realtime_scroll(page, start_y, end_y, secs_len - 0.4, mouse)
            t_e = time.time() - t_open
            f1 = await page.evaluate("window.__wdrFrames")
            segs.append({"order": s["order"], "start": t_s, "end": t_e, "start_y": start_y, "end_y": end_y,
                         "pageFps": round((f1 - f0) / max(t_e - t_s, 0.1), 1)})
        await ctx.close()
        webm = next(vid_dir.glob("*.webm"))
        for seg in segs:
            out = self.root / "recordings" / f"{seg['order']:02d}-desktop-scroll.mp4"
            dur = min(max(seg["end"] - seg["start"], 6.2), 11.8)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seg['start']:.2f}", "-i", str(webm), "-t", f"{dur:.2f}",
                            "-vf", "fps=25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(out)], check=True)
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                                   capture_output=True, text=True, check=True).stdout.strip()
            uniq = subprocess.run(["ffmpeg", "-i", str(out), "-vf", "mpdecimate", "-f", "null", "-"], capture_output=True, text=True).stderr
            m = re.findall(r"frame=\s*(\d+)", uniq)
            unique = int(m[-1]) if m else 0
            seg.update({"path": out.relative_to(self.root).as_posix(), "durationSeconds": round(float(probe), 3),
                        "uniqueFrames": unique, "effectiveFps": L.effective_fps(unique, float(probe))})
        shutil.rmtree(vid_dir, ignore_errors=True)
        self.recordings = segs
        self.mark("recordingsDone")

    async def variants(self, p, browser):
        g = self.root / "screenshots" / "_global"
        ctx = await browser.new_context(viewport={"width": DESKTOP[0], "height": DESKTOP[1]}, reduced_motion="reduce")
        page = await ctx.new_page()
        try:
            await self.load(page, "reduced-motion")
            await self.shot(page, g / "desktop-reduced-motion.png", "1440x900", "reduced-motion", "prefers-reduced-motion: reduce")
        except Exception as e:
            self.reduced_err = str(e)[:200]
        await ctx.close()
        b2 = await p.chromium.launch(headless=True, args=["--disable-webgl", "--disable-webgl2", "--disable-3d-apis"])
        page = await b2.new_page(viewport={"width": DESKTOP[0], "height": DESKTOP[1]})
        self.nowebgl_err = []
        page.on("pageerror", lambda e: self.nowebgl_err.append(str(e)[:300]))
        try:
            await self.load(page, "no-webgl")
            await self.shot(page, g / "desktop-no-webgl.png", "1440x900", "no-webgl", "chromium --disable-webgl --disable-3d-apis")
        except Exception as e:
            self.nowebgl_err.append(str(e)[:300])
        await b2.close()
        self.mark("variantsDone")

    def download_media(self):
        cap = self.a.media_cap_mb * 2**20
        aborted = {f["rawUrl"] for f in self.failed if f["type"] == "media" or L.classify(f["rawUrl"]) in ("video", "audio")}
        targets = {u for u, r in self.assets.items() if r["kind"] in ("video", "audio") and not r.get("cachedFile")} | aborted
        results = []
        for url in sorted(targets):
            if urlsplit(url).scheme not in ("http", "https"):
                continue
            rec = {"url": L.redact(url), "status": None}
            try:
                req = urllib.request.Request(url, headers={"Range": "bytes=0-", "User-Agent": "Mozilla/5.0 WebDesignRadar-kit"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    total = None
                    cr = r.headers.get("Content-Range")
                    if cr and "/" in cr and cr.split("/")[-1].isdigit():
                        total = int(cr.split("/")[-1])
                    elif (r.headers.get("Content-Length") or "").isdigit():
                        total = int(r.headers["Content-Length"])
                    plan = L.range_plan(total, cap)
                    rec.update({"bytesTotal": total, "plan": plan["action"], "httpStatus": r.status,
                                "contentType": r.headers.get("Content-Type")})
                    if plan["action"] == "metadata-only":
                        rec["status"] = "metadata-only"; rec["reason"] = plan["reason"]
                    else:
                        self.cache.mkdir(parents=True, exist_ok=True)
                        name = hashlib.sha256(url.encode()).hexdigest()[:12] + "-" + (Path(urlsplit(url).path).name or "media")[:60]
                        dest = self.cache / name; n = 0
                        with open(dest, "wb") as f:
                            while chunk := r.read(1 << 20):
                                n += len(chunk)
                                if n > cap:
                                    break
                                f.write(chunk)
                        if n > cap:
                            dest.unlink(); rec["status"] = "metadata-only"; rec["reason"] = f"stream exceeded cap {cap}"
                        else:
                            rec.update({"status": "downloaded", "cachedFile": str(dest), "bytes": n,
                                        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
            except Exception as e:
                rec["status"] = "failed"; rec["reason"] = str(e)[:200]
            results.append(rec)
            if url in self.assets:
                self.assets[url]["cachedFile"] = rec.get("cachedFile"); self.assets[url]["bytes"] = rec.get("bytes") or rec.get("bytesTotal")
            else:
                self.assets[url] = {"url": L.redact(url), "rawUrl": url, "kind": L.classify(url) or "video", "contentType": rec.get("contentType"),
                                    "status": rec.get("httpStatus"), "bytes": rec.get("bytes") or rec.get("bytesTotal"),
                                    "cachedFile": rec.get("cachedFile"), "firstSeen": "aborted-in-headless"}
        self.media = results
        self.mark("mediaDone")

    async def run(self):
        self.sections_ready = asyncio.get_running_loop().create_future()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=CHROME_ARGS)
            results = list(await asyncio.gather(self.desktop(browser), self.mobile(browser),
                                                self.variants(p, browser), return_exceptions=True))
            self.mark("parallelPhaseDone")
            # recording runs alone so the software renderer gets the CPU (higher real fps)
            results.append((await asyncio.gather(self.recorder(browser), return_exceptions=True))[0])
            await browser.close()
        errs = [repr(r)[:300] for r in results if isinstance(r, Exception)]
        if not self.sections_ready.done() or isinstance(results[0], Exception):
            raise SystemExit(f"desktop capture failed: {errs}")
        self.task_errors = errs
        if not self.a.no_media_download:
            await asyncio.to_thread(self.download_media)
        self.mark("total")
        self.write()

    def write(self):
        ev = self.root / "evidence"
        urls_all = list(self.network) + self.info["scripts"]
        script_hits = {lib: [L.redact(u)[:200] for u in urls_all if re.search(rx, u, re.I)][:3]
                       for lib, rx in LIB_SCRIPT_PATTERNS.items() if any(re.search(rx, u, re.I) for u in urls_all)}
        counts = {}
        for v in self.network.values():
            counts[v["type"]] = counts.get(v["type"], 0) + 1
        rec_by = {r["order"]: r for r in getattr(self, "recordings", [])}
        index = []
        for s in self.sections:
            e = {"order": s["order"], "top": s["top"], "height": s["height"], "selector": s.get("selector"),
                 "domHint": {k: s.get(k) for k in ("tag", "id", "cls", "text", "bg")}, "mobile": s.get("mobile"),
                 "name": f"Section {s['order']:02d}（待命名）", "document": f"sections/{s['order']:02d}-待命名.md",
                 "screenshots": [{k: c[k] for k in ("path", "viewport", "state", "trigger")} for c in s.get("captures", []) + ([s["mobileCapture"]] if s.get("mobileCapture") else [])]}
            r = rec_by.get(s["order"])
            if r:
                e["motionCaptureRequired"] = True
                e["video"] = {"path": r["path"], "durationSeconds": r["durationSeconds"], "captureMethod": "playwright-record-video",
                              "interaction": f"从 y={r['start_y']} 用页面内 requestAnimationFrame 按真实时间（easeInOut）滚动到 y={r['end_y']}，同时指针从左 20% 移到右 80% 并正弦上下摆动",
                              "uniqueFrames": r["uniqueFrames"], "effectiveFps": r["effectiveFps"], "pageFps": r["pageFps"]}
            index.append(e)
        cleaned_assets = [{k: v for k, v in r.items() if k != "rawUrl"} for r in self.assets.values()]
        summary = {
            "url": self.a.url, "finalUrl": getattr(self, "final_url", None), "capturedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "browserUsed": "playwright-chromium", "captureTool": "capture/capture.py v2", "fast": self.a.fast,
            "viewports": {"desktop": "1440x900", "mobile": "390x844"}, "timingsSeconds": self.timings, "loadSeconds": getattr(self, "summary_load", None),
            "page": {**{k: self.info[k] for k in ("title", "lang", "docHeight", "dpr", "fonts")}, "mobileDocHeight": getattr(self, "mobile_doc_h", None)},
            "webgl": self.webgl, "accessWallSuspected": self.wall,
            "consent": self.consent,
            "libraries": {"runtimeGlobals": self.info["globals"], "scriptUrlMatches": script_hits, "note": "presence only"},
            "sectionDetection": self.detection,
            "recordings": getattr(self, "recordings", []),
            "lifecycle": self.lifecycle,
            "consoleErrors": self.console[:80], "pageErrors": self.page_errors[:40],
            "failedRequests": [{k: v for k, v in f.items() if k != "rawUrl"} for f in self.failed[:80]],
            "requestCounts": counts, "noWebglPageErrors": getattr(self, "nowebgl_err", [])[:10],
            "mediaDownloads": getattr(self, "media", []), "assets": sorted(cleaned_assets, key=lambda r: (r["kind"], -(r["bytes"] or 0))),
            "taskErrors": self.task_errors, "rawAnalysisDir": str(self.raw), "screenshots": self.shots,
        }
        (ev / "capture-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (ev / "section-index.draft.json").write_text(json.dumps({"url": self.a.url, "detection": self.detection, "sections": index}, ensure_ascii=False, indent=2), encoding="utf-8")
        base = {"capturedAt": summary["capturedAt"]}
        evs = {
            "EV-CAP-1": ("runtime-behavior", "evidence/capture-summary.json#libraries", "window globals + script URL matches (presence only)"),
            "EV-CAP-2": ("network-request", "evidence/capture-summary.json#assets", f"{len(self.assets)} asset responses, {len(self.failed)} failed requests"),
            "EV-CAP-3": ("visual-capture", "screenshots/_global/", "desktop/mobile load, stepwise scroll, reduced-motion, no-webgl captures"),
            "EV-CAP-4": ("runtime-behavior", "evidence/capture-summary.json#webgl", "WebGL/WebGPU capability"),
            "EV-CAP-5": ("runtime-behavior", "evidence/capture-summary.json#lifecycle", "resize / visibility / reload checks with canvas state"),
            "EV-CAP-6": ("visual-capture", "recordings/", "Playwright native recordings of real-time smooth scroll"),
        }
        for k, (st, src, n) in evs.items():
            (ev / f"{k}.json").write_text(json.dumps({"id": k, "sourceType": st, "source": src, "notes": n, **base}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "captured", "sections": len(index), "screenshots": len(self.shots), "assets": len(self.assets),
                          "consentClicked": sum(len(c["clicked"]) for c in self.consent), "timings": self.timings,
                          "recordFps": [r.get("effectiveFps") for r in getattr(self, "recordings", [])],
                          "media": [(m["status"], m.get("bytes") or m.get("bytesTotal")) for m in getattr(self, "media", [])],
                          "taskErrors": self.task_errors, "summary": str(ev / "capture-summary.json")}, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--staging", required=True, help="the run's stagingDir")
    ap.add_argument("--max-sections", type=int, default=6)
    ap.add_argument("--video-seconds", type=float, default=8.0)
    ap.add_argument("--record-width", type=int, default=1280, help="recording output width (viewport stays 1440x900)")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--fast", action="store_true", help="shorter waits, every 3rd scroll step, 7s recordings")
    ap.add_argument("--cache-assets", action="store_true", help="cache model/texture/font/shader bodies (<=25MB) outside staging")
    ap.add_argument("--no-media-download", action="store_true")
    ap.add_argument("--media-cap-mb", type=int, default=60)
    ap.add_argument("--timeout", type=int, default=45000)
    a = ap.parse_args()
    if a.fast and a.video_seconds == 8.0:
        a.video_seconds = 7.0
    if urlsplit(a.url).scheme not in ("http", "https"):
        raise SystemExit("only public http(s) URLs")
    asyncio.run(Cap(a).run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
