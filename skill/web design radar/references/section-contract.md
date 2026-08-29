# Section 文档交付契约

用户可见结果必须以中文为主。技术名、API、类名、属性名、Shader uniform 和代码保留英文原名，但解释必须是中文。

最终结果固定为：

- `00-网站整体前端技术总结.md`：唯一一份网站级总览，合并架构、技术栈、全局动效、资源链、复刻工程方案和总体验收。
- `sections/NN-中文名称.md`：一个 Section 对应一个 Markdown。首页实际有几个视觉/叙事 Section，就必须生成几个文件，连续编号并由总览链接；不得把多个明显独立的 Section 合并成一篇。
- `evidence/section-index.json`：在观察阶段按页面真实顺序记录 `order`、`name`、`document`、`evidenceIds`。验证器以它核对 Section 文档数量和一一对应关系。
- `screenshots/NN-name/`：每个 Section 至少 4 张不同状态截图，覆盖桌面初始、桌面交互/滚动中、桌面结束/变化后、移动端代表状态。
- `recordings/`：含动画、Hover、Pointer/Touch、拖拽、滚动联动、视频状态变化或 WebGL/3D/Shader 的 Section 必须有一段 6–12 秒交互录屏；静态 Section 须记录中文省略原因。
- `assets/`、`screenshots/`、`recordings/`、`evidence/` 和 JSON manifest 只作为文档引用的证据/资源附件。

完整 HTML、CSS、JavaScript bundle、反编译页面或临时抓取文件不属于最终交付。只把支持结论的短源码片段写进 Markdown 或 evidence 文本；原始抓取内容必须在验证前移出 `stagingDir` 或删除。

每份 Section 文档必须足够让另一个 Agent 从空项目开始编码，不得只罗列技术名。正文至少覆盖以下内容；确实不适用时写 `N/A — <中文原因>`。

1. 效果目标和可观察视觉结果。
2. Evidence table: claim, confidence label, evidence ID, limitation.
3. DOM/Canvas/media layer tree.
4. Layout and composition: position, overflow, clip/mask, blend mode, z-index.
5. Typography, color, spacing, size, breakpoints.
6. Enter, loop, pointer/touch, scroll, and exit timing.
7. 视觉证据：逐张嵌入截图并说明视口、触发动作、前后变化；链接录屏并说明完整交互路径。
8. Animation implementation: library, trigger, start/end, scrub, pin, easing, duration, cleanup.
9. Three.js/WebGL: renderer, camera, objects, geometry, materials, lights, render targets, postprocessing, DPR, resize, dispose.
10. Shader: pass order, vertex/fragment roles, uniforms, texture inputs, coordinate system, blend math, frame feedback. Mark equivalent code `inferred`.
11. Resource mapping: public URL, local path, purpose, hash, decoder dependencies, fallback.
12. Reproduction steps from an empty project, dependencies, pseudocode/interfaces.
13. Acceptance: desktop, mobile, reduced-motion, missing resource, and no-WebGL states.
14. Known differences and human judgments still required.

## Layer notation

Show paint order front-to-back and ownership:

```text
page
├── z0 media/video
├── z1 WebGL canvas
│   ├── scene render target
│   └── postprocess / fluid mask
├── z2 semantic HTML content
└── z3 pointer and navigation overlays
```

Also state whether the canvas is fixed, sticky, or section-bound; how DOM bounds map into shader UV/clip space; and which layer owns pointer events.

验收标准必须可观察：写明视口、滚动位置、指针路径、预期控制台/网络状态、生命周期动作和视觉容差。总览正文不得少于 1200 个非空白字符、200 个中文字符；每个 Section 不得少于 900 个非空白字符、120 个中文字符，并至少包含一段层级树、伪代码、接口或实现代码块。
