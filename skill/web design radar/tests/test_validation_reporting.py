import hashlib
import json
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from support import import_package

import_package()

from web_design_radar.db import connect
from web_design_radar.migrations import migrate
from web_design_radar.reporting import finalize_day, finalize_one_off
from web_design_radar.runs import RunStore
from web_design_radar.scoring import Candidate
from web_design_radar.validation import validate_case


def png(rgb: tuple[int, int, int]) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = b"\x00" + bytes(rgb)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def write_video(path: Path, duration: int = 8) -> None:
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "color=c=black:s=16x16:r=2", "-t", str(duration), "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(path),
        ],
        check=True,
        capture_output=True,
    )
SECTION = """# 01 Hero

## Evidence
- observed: EV-1

## Layer Tree
```text
page > canvas > ui
```

## Responsive
Desktop and mobile use different camera framing.

## Resources
[scene model](../assets/models/scene.glb)

## Reproduction Steps
1. Build the semantic DOM.
2. Add the WebGL canvas.

## Acceptance
Verify pointer response, mobile framing, fallback, and cleanup.
"""

CHINESE_OVERVIEW = """# 网站整体前端技术总结

## 网站与体验概览
这个首页通过语义化内容层、固定的视觉渲染层和页面级交互层共同构成。本文说明真实观察、源码证据、推断边界以及从空项目开始复刻时所需的工程顺序。

## 首页 Section 清单
- [01 Hero](sections/01-hero.md)

## 全局前端技术栈
页面包含响应式布局、滚动状态管理、WebGL 渲染与资源加载。每项技术结论都应绑定证据，不能因为检测到库就直接认定某个效果由该库实现。

## 页面级层级关系
```text
页面根节点
├── 固定 WebGL 画布
├── 语义化 HTML 内容
└── 导航与指针交互层
```

## 全局动效与渲染流程
输入事件先更新统一状态，再由布局、时间线和渲染循环消费。窗口尺寸变化时同步更新断点、像素比、相机和渲染目标。

## 公共资源与依赖
模型、纹理、字体与解码器必须记录公开来源、本地路径、用途、哈希、授权状态及失败回退方式。

## 从零复刻的工程方案
先实现语义结构和静态视觉，再加入滚动与指针动效，最后接入 WebGL、Shader、响应式和降级路径。实现时保留清理函数与 reduced-motion 分支。

## 跨 Section 响应式与降级策略
桌面端与移动端分别验证布局、触摸输入、资源失败、无 WebGL 和 reduced-motion 状态，不能只依赖缩放桌面截图。

## 验收标准
在 1440×900 与 390×844 视口检查首屏、滚动中段和页尾；控制台无未处理异常，资源请求没有意外失败，刷新、返回和尺寸变化后状态可以恢复。

## 证据、置信度与未知项
所有结论标记 source-confirmed、observed、inferred 或 unknown。当前示例只确认指针响应，具体帧缓冲实现仍需更多源码证据。
""" + ("补充说明：全局变量、组件职责、生命周期、性能边界和资源依赖都必须在复刻前逐项核对。\n" * 30)

CHINESE_SECTION = """# 01 首屏 Hero

## 效果目标
首屏需要同时还原文字、背景画布和指针反馈，视觉目标包括构图、遮罩边缘、滚动离场以及移动端触摸反馈。

## 前端技术结论
语义内容由 HTML 负责，布局由 CSS 响应式规则负责，实时视觉由 WebGL 画布负责。检测到某个库只代表它存在，效果归属仍需调用点或运行轨迹证明。

## 层级关系
```text
Hero Section
├── z0 背景媒体
├── z1 WebGL 画布
└── z2 标题与导航
```

## 布局与样式参数
桌面端画布固定铺满视口，内容使用网格对齐；移动端调整字号、留白和相机取景。明确记录 position、overflow、z-index、混合模式和断点。

## 动效与交互时间线
进入阶段完成资源淡入，循环阶段更新渲染，指针阶段写入归一化坐标，滚动阶段驱动离场。退出或卸载时移除监听并释放 GPU 资源。

## 视觉证据：截图与录屏
![桌面初始状态](../screenshots/01-hero/desktop-rest.png)
![桌面交互中状态](../screenshots/01-hero/desktop-active.png)
![桌面滚动结束状态](../screenshots/01-hero/desktop-exit.png)
![移动端触摸状态](../screenshots/01-hero/mobile-active.png)
[查看 Hero 指针交互录屏](../recordings/01-hero-interaction.mp4)

录屏从静止状态开始，指针横向移动后向下滚动，展示遮罩扩散、残影衰减和 Section 离场过程。

## WebGL、3D 与 Shader 实现
渲染器限制像素比并监听尺寸变化；Shader 接收时间、分辨率、指针和纹理 uniform。若真实 pass 顺序未确认，则使用 inferred 标记等价实现。

```js
function update(pointer, time) {
  uniforms.uPointer.value.copy(pointer)
  uniforms.uTime.value = time
  renderer.render(scene, camera)
}
```

## 资源清单
模型或纹理记录公开 URL、本地路径、哈希、用途、授权状态、解码依赖与缺失时的静态回退图。

## 实现方法与组件职责
Hero 组件只管理 DOM 生命周期，渲染控制器管理场景、Shader 和资源，输入控制器把 pointer/touch 转换成统一坐标，避免职责交叉。

## 从空项目复刻步骤
1. 建立语义结构并完成静态构图。
2. 接入响应式断点和字体。
3. 创建画布、相机和渲染循环。
4. 接入指针、滚动和降级分支。
5. 完成桌面与移动端验收。

## 验收标准
在桌面和移动视口检查加载前后、指针横移、触摸拖动、50% 滚动与离场状态；同时验证 reduced-motion、资源丢失、WebGL 不可用和组件卸载。

## 证据与可信度
指针响应为 observed，证据为 EV-1；具体 Shader 反馈结构暂为 inferred，必须在复刻文档中保留这一限制。

## 已知差异与待确认项
示例尚未确认原站缓动曲线与 framebuffer 精度，复刻时应先匹配可观察结果，再决定是否使用等价实现。
""" + ("实现补充：逐项记录触发条件、关键数值、清理方式、移动端差异和视觉容差。\n" * 24)


def write_case(root: Path) -> None:
    (root / "sections").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "models").mkdir(parents=True, exist_ok=True)
    (root / "screenshots" / "01-hero").mkdir(parents=True, exist_ok=True)
    (root / "recordings").mkdir(parents=True, exist_ok=True)
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "00-网站整体前端技术总结.md").write_text(CHINESE_OVERVIEW, encoding="utf-8")
    (root / "sections" / "01-hero.md").write_text(CHINESE_SECTION, encoding="utf-8")
    model = b"glTF"
    (root / "assets" / "models" / "scene.glb").write_bytes(model)
    captures = {
        "desktop-rest.png": (10, 20, 30),
        "desktop-active.png": (40, 50, 60),
        "desktop-exit.png": (70, 80, 90),
        "mobile-active.png": (100, 110, 120),
    }
    for name, color in captures.items():
        (root / "screenshots" / "01-hero" / name).write_bytes(png(color))
    write_video(root / "recordings" / "01-hero-interaction.mp4")
    (root / "evidence" / "EV-1.json").write_text(
        json.dumps({"id": "EV-1", "sourceType": "runtime-behavior"}), encoding="utf-8"
    )
    (root / "evidence" / "claims.json").write_text(
        json.dumps({
            "claims": [{
                "id": "CLAIM-1", "claim": "Hero responds to pointer input",
                "confidence": "observed", "evidenceIds": ["EV-1"]
            }]
        }),
        encoding="utf-8",
    )
    (root / "evidence" / "section-index.json").write_text(
        json.dumps({
            "sections": [{
                "order": 1,
                "name": "首屏 Hero",
                "document": "sections/01-hero.md",
                "evidenceIds": ["EV-1"],
                "motionCaptureRequired": True,
                "screenshots": [
                    {"path": "screenshots/01-hero/desktop-rest.png", "viewport": "1440x900", "state": "初始静止", "trigger": "loader 完成"},
                    {"path": "screenshots/01-hero/desktop-active.png", "viewport": "1440x900", "state": "指针交互中", "trigger": "pointer 横移"},
                    {"path": "screenshots/01-hero/desktop-exit.png", "viewport": "1440x900", "state": "滚动离场", "trigger": "滚动至 Section 末端"},
                    {"path": "screenshots/01-hero/mobile-active.png", "viewport": "390x844", "state": "移动端触摸", "trigger": "touch 拖动"},
                ],
                "video": {
                    "path": "recordings/01-hero-interaction.mp4",
                    "durationSeconds": 8,
                    "captureMethod": "playwright-video",
                    "interaction": "静止 → pointer 横移 → 滚动离场"
                },
            }]
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "asset-manifest.json").write_text(
        json.dumps({
            "assets": [{
                "id": "ASSET-1", "type": "model",
                "originalUrl": "https://cdn.example/scene.glb",
                "localPath": "assets/models/scene.glb",
                "sha256": hashlib.sha256(model).hexdigest(), "bytes": len(model),
                "mimeType": "model/gltf-binary", "usedBy": ["01-hero"],
                "access": "public-page-request", "license": "unknown",
                "status": "downloaded"
            }]
        }),
        encoding="utf-8",
    )
    (root / "run-manifest.json").write_text(json.dumps({"runId": "synthetic"}), encoding="utf-8")


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "case"
        write_case(self.root)

    def test_valid_case_passes_with_evidence_assets_and_both_viewports(self):
        """Catches a validator that rejects the documented happy path."""
        report = validate_case(self.root)
        self.assertTrue(report.passed, report.issues)
        self.assertEqual(report.issues, [])

    def test_missing_asset_broken_link_mobile_gap_and_unsupported_claim_are_reported(self):
        """Catches silent gaps that would block a later replication agent."""
        (self.root / "assets/models/scene.glb").unlink()
        with (self.root / "00-网站整体前端技术总结.md").open("a", encoding="utf-8") as stream:
            stream.write("[missing](missing.md)\n")
        (self.root / "screenshots/01-hero/mobile-active.png").unlink()
        (self.root / "evidence/claims.json").write_text(
            json.dumps({"claims": [{
                "id": "CLAIM-1", "claim": "Pointer effect", "confidence": "observed",
                "evidenceIds": []
            }]}),
            encoding="utf-8",
        )
        codes = {issue.code for issue in validate_case(self.root).issues}
        self.assertTrue({
            "missing-asset", "broken-link", "missing-mobile-screenshot",
            "unsupported-observed-claim"
        }.issubset(codes))

    def test_thin_or_english_only_markdown_is_rejected(self):
        """Catches shallow scaffolds that are not usable as Chinese replication briefs."""
        (self.root / "00-网站整体前端技术总结.md").write_text(
            "# Frontend overview\n\nGSAP and WebGL are used.\n", encoding="utf-8"
        )
        (self.root / "sections/01-hero.md").write_text(SECTION, encoding="utf-8")

        codes = {issue.code for issue in validate_case(self.root).issues}
        self.assertIn("shallow-overall-summary", codes)
        self.assertIn("non-chinese-primary-document", codes)
        self.assertIn("shallow-section-document", codes)

    def test_raw_html_css_and_javascript_are_not_final_deliverables(self):
        """Catches extraction artifacts leaking into the user-facing result folder."""
        (self.root / "homepage.html").write_text("<main></main>", encoding="utf-8")
        (self.root / "site.css").write_text("main{}", encoding="utf-8")
        (self.root / "main.js").write_text("export default 1", encoding="utf-8")

        issues = validate_case(self.root).issues
        leaked = [issue.path for issue in issues if issue.code == "raw-source-deliverable"]
        self.assertEqual(leaked, ["homepage.html", "main.js", "site.css"])

    def test_every_observed_homepage_section_requires_one_matching_markdown(self):
        """Catches a worker documenting only the hero while silently omitting later sections."""
        (self.root / "evidence/section-index.json").write_text(
            json.dumps({
                "sections": [
                    {"order": 1, "name": "首屏 Hero", "document": "sections/01-hero.md", "evidenceIds": ["EV-1"]},
                    {"order": 2, "name": "项目展示", "document": "sections/02-projects.md", "evidenceIds": ["EV-1"]},
                ]
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        issues = validate_case(self.root).issues
        codes = {issue.code for issue in issues}
        self.assertIn("section-count-mismatch", codes)
        self.assertIn("missing-section-document", codes)

    def test_each_section_requires_multiple_states_and_video_for_motion(self):
        """Catches one-screenshot summaries that miss interaction-dependent visual states."""
        index_path = self.root / "evidence/section-index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        section = index["sections"][0]
        section["screenshots"] = section["screenshots"][:2]
        section["video"] = None
        index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

        codes = {issue.code for issue in validate_case(self.root).issues}
        self.assertIn("insufficient-section-screenshots", codes)
        self.assertIn("missing-section-mobile-screenshot", codes)
        self.assertIn("missing-section-video", codes)

    def test_section_markdown_must_reference_every_declared_capture(self):
        """Catches useful media being dumped into folders without explanation in the brief."""
        document = self.root / "sections/01-hero.md"
        text = document.read_text(encoding="utf-8")
        document.write_text(
            text.replace("![桌面交互中状态](../screenshots/01-hero/desktop-active.png)\n", ""),
            encoding="utf-8",
        )

        issues = validate_case(self.root).issues
        self.assertTrue(any(
            issue.code == "unreferenced-section-media"
            and issue.path == "screenshots/01-hero/desktop-active.png"
            for issue in issues
        ))

    def test_byte_identical_section_screenshots_are_rejected(self):
        """Catches four differently named files containing the same visual capture bytes."""
        source = self.root / "screenshots/01-hero/desktop-rest.png"
        duplicate = self.root / "screenshots/01-hero/desktop-active.png"
        duplicate.write_bytes(source.read_bytes())

        codes = {issue.code for issue in validate_case(self.root).issues}
        self.assertIn("duplicate-section-screenshot-content", codes)

    def test_fake_video_header_is_rejected_by_ffprobe(self):
        """Catches a fabricated MP4 header with no decodable video stream."""
        video = self.root / "recordings/01-hero-interaction.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"not-a-video")

        codes = {issue.code for issue in validate_case(self.root).issues}
        self.assertIn("invalid-section-video-stream", codes)

    def test_real_video_duration_must_match_six_to_twelve_second_contract(self):
        """Catches forged JSON duration and a playable clip outside the documented range."""
        video = self.root / "recordings/01-hero-interaction.mp4"
        write_video(video, duration=14)

        codes = {issue.code for issue in validate_case(self.root).issues}
        self.assertIn("invalid-section-video-duration", codes)
        self.assertIn("section-video-duration-mismatch", codes)


class ReportingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.db = connect(self.root / "state/radar.sqlite3")
        self.addCleanup(self.db.close)
        migrate(self.db)
        self.store = RunStore(self.db, self.root)
        candidates = [
            Candidate("https://a.example", "https://awwwards.com/a", "A", 1, 1, 1, 1, 1, ("webgl",)),
            Candidate("https://b.example", "https://awwwards.com/b", "B", .9, .9, .9, .9, .9, ("gsap",)),
        ]
        self.runs = self.store.start_batch(
            "2026-08-29", candidates, "2026-08-29T02:00:00+08:00"
        )
        write_case(self.runs[0].staging_dir)
        self.db.execute(
            "UPDATE site_runs SET state='ready_to_publish',current_stage='validating' WHERE run_id=?",
            (self.runs[0].run_id,),
        )
        self.db.execute(
            "UPDATE site_runs SET state='assets',current_stage='assets' WHERE run_id=?",
            (self.runs[1].run_id,),
        )
        self.db.commit()

    def state(self, run_id):
        return self.db.execute(
            "SELECT state FROM site_runs WHERE run_id=?", (run_id,)
        ).fetchone()[0]

    def test_closeout_publishes_ready_run_but_keeps_other_run_resumable(self):
        """Catches 08:30 closeout prematurely freezing recoverable work."""
        result = finalize_day(
            self.db, self.root, "2026-08-29", "2026-08-29T08:30:00+08:00",
            force_deadline=False,
        )
        self.assertEqual(self.state(self.runs[0].run_id), "completed")
        self.assertEqual(self.state(self.runs[1].run_id), "assets")
        self.assertEqual(result.completed, 1)
        self.assertEqual(result.active, 1)
        self.assertTrue(self.runs[0].revision_dir.is_dir())

    def test_deadline_freezes_partial_and_terminal_report_is_idempotent(self):
        """Catches unfinished work disappearing or changing report totals on retry."""
        finalize_day(
            self.db, self.root, "2026-08-29", "2026-08-29T08:30:00+08:00",
            force_deadline=False,
        )
        result = finalize_day(
            self.db, self.root, "2026-08-29", "2026-08-29T09:00:00+08:00",
            force_deadline=True,
        )
        report_bytes = result.report_path.read_bytes()
        repeated = finalize_day(
            self.db, self.root, "2026-08-29", "2026-08-29T09:00:00+08:00",
            force_deadline=True,
        )
        self.assertEqual(self.state(self.runs[1].run_id), "partial")
        self.assertEqual((result.completed, result.partial, result.active), (1, 1, 0))
        self.assertIn("1/2 completed", report_bytes.decode("utf-8"))
        self.assertEqual(report_bytes, repeated.report_path.read_bytes())

    def test_one_off_ready_run_publishes_to_its_timestamped_result_folder(self):
        """Catches one-off runs remaining forever in ready_to_publish."""
        candidate = Candidate(
            "https://manual.example", "https://manual.example", "Manual", 1, 1, 1, 1, 1, tuple()
        )
        run = self.store.start_one_off(candidate, "2026-08-30T10:00:00+08:00")
        write_case(run.staging_dir)
        self.db.execute(
            "UPDATE site_runs SET state='ready_to_publish',current_stage='validating' WHERE run_id=?",
            (run.run_id,),
        )
        self.db.commit()

        result = finalize_one_off(self.db, self.root, run.run_id, "2026-08-30T10:30:00+08:00")

        self.assertTrue(result.published)
        self.assertEqual(result.state, "completed")
        self.assertTrue(run.revision_dir.is_dir())
        self.assertFalse(run.staging_dir.exists())

    def test_invalid_one_off_returns_to_validating_instead_of_becoming_terminal(self):
        """Catches failed one-off publication becoming impossible to repair and retry."""
        candidate = Candidate(
            "https://manual.example", "https://manual.example", "Manual", 1, 1, 1, 1, 1, tuple()
        )
        run = self.store.start_one_off(candidate, "2026-08-30T10:00:00+08:00")
        self.db.execute(
            "UPDATE site_runs SET state='ready_to_publish',current_stage='validating' WHERE run_id=?",
            (run.run_id,),
        )
        self.db.commit()

        result = finalize_one_off(self.db, self.root, run.run_id, "2026-08-30T10:30:00+08:00")

        self.assertFalse(result.published)
        self.assertEqual(result.state, "assigned")
        self.assertTrue(run.staging_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
