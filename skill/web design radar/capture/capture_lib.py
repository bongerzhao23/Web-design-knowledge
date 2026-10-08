"""Pure, standard-library helpers for capture.py (unit-tested in tests/test_capture_lib.py)."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

ACCEPT_WORDS = [
    "accept all", "accept all cookies", "accept cookies", "accept", "allow all", "allow all cookies", "allow cookies", "allow",
    "agree", "i agree", "agree and close", "got it", "ok", "okay", "i understand", "understood", "continue", "confirm", "yes",
    "accepter", "tout accepter", "j'accepte", "accepter et fermer", "d'accord",
    "akzeptieren", "alle akzeptieren", "zustimmen", "einverstanden", "verstanden",
    "aceptar", "aceptar todo", "acepto", "de acuerdo", "aceitar", "aceitar todos", "concordo",
    "accetta", "accetta tutto", "accetto", "accetta tutti", "accepteren", "alles accepteren", "akkoord",
    "godkänn", "acceptera", "godta", "accepter alle", "hyväksy", "zaakceptuj", "akceptuję", "souhlasím", "elfogadom",
    "принять", "согласен", "kabul et", "同意", "接受", "全部接受", "接受全部", "我同意", "同意并继续", "好的", "知道了", "允许",
    "すべて同意", "同意する", "受け入れる", "모두 동의", "동의", "수락",
]
FORBIDDEN = re.compile(r"log ?in|sign ?in|sign ?up|register|subscribe|subscription|newsletter|create account|password|buy|checkout|"
                       r"登录|登入|注册|订阅|购买|abonn|s'inscrire|anmelden|registrieren|suscrib|iscriv", re.I)
CONSENT_CONTEXT = re.compile(r"cookie|consent|gdpr|ccpa|privacy|tracking|personal data|datenschutz|confidentialit|"
                             r"privacidad|riservatezza|隐私|隱私|个人信息|クッキー|쿠키|rgpd|traceurs", re.I)

KNOWN_CMP_SELECTORS = [
    ("OneTrust", "#onetrust-accept-btn-handler"),
    ("OneTrust", "#accept-recommended-btn-handler"),
    ("Cookiebot", "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"),
    ("Cookiebot", "#CybotCookiebotDialogBodyButtonAccept"),
    ("Didomi", "#didomi-notice-agree-button"),
    ("Usercentrics", "[data-testid='uc-accept-all-button']"),
    ("Quantcast", ".qc-cmp2-summary-buttons button[mode='primary']"),
    ("TrustArc", "#truste-consent-button"),
    ("Iubenda", ".iubenda-cs-accept-btn"),
    ("Complianz", ".cmplz-accept"),
    ("CookieYes", ".cky-btn-accept"),
    ("Osano", ".osano-cm-accept-all"),
    ("Borlabs", "a[data-cookie-accept-all]"),
    ("Klaro", ".cm-btn-accept-all"),
    ("Termly", "[data-tid='banner-accept']"),
    ("Finsweet/Webflow consent", "[fs-cc='allow']"),
    ("Webflow consent", "[data-consent='accept'], [data-cookie-consent='accept']"),
    ("Axeptio", "#axeptio_btn_acceptAll"),
    ("Sirdata/Generic TCF", "button.sd-cmp-accept, button.tcf-accept"),
]

CONSENT_HIDE_CSS = """
#onetrust-consent-sdk, #onetrust-banner-sdk, #CybotCookiebotDialog, #didomi-host, #usercentrics-root, .qc-cmp2-container,
#truste-consent-track, .iubenda-cs-container, .cmplz-cookiebanner, .cky-consent-container, .osano-cm-window, #BorlabsCookieBox,
.klaro, #termly-code-snippet-support, [fs-cc='banner'], #axeptio_overlay, .cookie-banner, .cookie-consent, #cookie-banner,
#cookie-consent, [class*='cookie-banner'], [id*='cookie-banner'], [aria-label*='cookie' i] { display: none !important; }
"""


def normalize_label(text: str) -> str:
    text = re.sub(r"[\s\u00a0]+", " ", (text or "")).strip().lower()
    return text.strip(" .!→>✓×")


def is_forbidden_label(text: str) -> bool:
    return bool(FORBIDDEN.search(text or ""))


def is_accept_label(text: str) -> bool:
    label = normalize_label(text)
    if not label or len(label) > 40 or is_forbidden_label(label):
        return False
    return label in ACCEPT_WORDS or any(label.startswith(w + " ") and len(label) <= len(w) + 14 for w in ACCEPT_WORDS if len(w) > 3)


def is_consent_context(text: str) -> bool:
    return bool(CONSENT_CONTEXT.search(text or ""))


ASSET_RULES = [
    ("model", re.compile(r"\.(glb|gltf|fbx|obj|usdz|drc|ktx2|basis|hdr|exr)(\?|$)", re.I)),
    ("shader", re.compile(r"\.(glsl|vert|frag|vs|fs|wgsl)(\?|$)", re.I)),
    ("font", re.compile(r"\.(woff2?|ttf|otf|eot)(\?|$)", re.I)),
    ("video", re.compile(r"\.(mp4|webm|mov|m3u8|m4v)(\?|$)", re.I)),
    ("texture", re.compile(r"\.(png|jpe?g|webp|avif|gif|svg|ktx)(\?|$)", re.I)),
    ("audio", re.compile(r"\.(mp3|ogg|wav|m4a)(\?|$)", re.I)),
]


def classify(url: str, ctype: str = "", rtype: str = "") -> str | None:
    path = urlsplit(url).path
    for name, rx in ASSET_RULES:
        if rx.search(path):
            return name
    ct = (ctype or "").lower()
    if "model/" in ct or "gltf" in ct:
        return "model"
    if "font" in ct:
        return "font"
    if ct.startswith("video/"):
        return "video"
    if ct.startswith("audio/"):
        return "audio"
    if ct.startswith("image/"):
        return "texture"
    return {"font": "font", "media": "video"}.get(rtype)


def redact(url: str) -> str:
    return re.sub(r"(?i)([?&](token|sig|signature|key|auth|expires|x-amz-[^=]*|policy|hdnts|hmac)=)[^&]+", r"\1REDACTED", url)


def choose_sections(candidates: list[dict], doc_height: int, viewport_h: int, max_sections: int,
                    min_height_ratio: float = 0.35) -> list[dict]:
    """Pick an ordered, non-overlapping cover of the page from candidate blocks.

    candidates: {top, height, width_ratio, semantic(bool), depth, bg, selector}. Preference: full width,
    semantic tags, shallower depth. Blocks shorter than min_height_ratio*vh are dropped; blocks that cover
    >90% of the page are containers, not sections. Consecutive blocks with the same background and tiny
    height are merged into the previous block.
    """
    min_h = viewport_h * min_height_ratio
    norm = []
    for c in candidates:  # pinned/translated blocks can report a negative top; clip to the document
        c = dict(c)
        if c.get("top", 0) < 0:
            c["height"] = c.get("height", 0) + c["top"]
            c["top"] = 0
        norm.append(c)
    candidates = norm
    pool = [c for c in candidates
            if c.get("height", 0) >= min_h and c.get("width_ratio", 1) >= 0.9 and c.get("height", 0) < doc_height * 0.9]
    pool.sort(key=lambda c: (c["top"], -int(bool(c.get("semantic"))), c.get("depth", 0), -c["height"]))
    chosen: list[dict] = []
    for c in pool:
        if chosen:
            last = chosen[-1]
            last_bottom = last["top"] + last["height"]
            overlap = last_bottom - c["top"]
            if overlap > c["height"] * 0.5:
                if c["top"] + c["height"] <= last_bottom + 2:
                    continue  # nested child of the previous block
                if c["top"] - last["top"] < min_h:
                    continue
                last["height"] = c["top"] - last["top"]  # sibling overlapping via pin/transform: trim previous
        chosen.append(dict(c))
    merged: list[dict] = []
    for c in chosen:
        if merged and c["height"] < viewport_h * 0.5 and c.get("bg") and c.get("bg") == merged[-1].get("bg"):
            merged[-1]["height"] = c["top"] + c["height"] - merged[-1]["top"]
            continue
        merged.append(c)
    for i, c in enumerate(merged, 1):
        c["order"] = i
    if len(merged) < 2:
        n = max(1, min(max_sections, round(doc_height / viewport_h)))
        return [{"order": i + 1, "top": i * viewport_h, "height": viewport_h, "selector": None, "semantic": False,
                 "method": "viewport-slice"} for i in range(n)]
    return merged[:max_sections]


def range_plan(total: int | None, cap: int) -> dict:
    """Decide how to download a media file of `total` bytes under `cap`."""
    if total is None:
        return {"action": "stream-with-cap", "range": None}
    if total <= cap:
        return {"action": "download", "range": None}
    return {"action": "metadata-only", "reason": f"size {total} exceeds cap {cap}"}


def effective_fps(unique_frames: int, seconds: float) -> float:
    return round(unique_frames / seconds, 1) if seconds > 0 else 0.0
