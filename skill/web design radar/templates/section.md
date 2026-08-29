# NN｜Section 中文名称

## 效果目标

用中文描述静态画面、进入、循环、滚动、指针/触摸和离场时用户实际看到的结果。

## 前端技术结论

| 技术 | 在本 Section 中的职责 | 可信度 | 证据 ID | 限制 |
|---|---|---|---|---|

## 层级关系

```text
Section 根节点
├── z0 背景媒体
├── z1 Canvas/WebGL
├── z2 文本与内容
└── z3 交互覆盖层
```

写清 DOM、Canvas、视频和覆盖层的前后顺序、定位方式、裁切边界与事件归属。

## 布局与样式参数

记录 position、display/grid、尺寸、间距、字体、颜色、overflow、clip/mask、blend-mode、z-index、断点与移动端变化。尽量提供可执行数值。

## 动效与交互时间线

按进入、循环、pointer/touch、scroll 和退出列出 trigger、start/end、scrub、pin、ease、duration、关键状态和清理动作。

## 视觉证据：截图与录屏

逐张嵌入本 Section 的截图，并在中文图注中写明视口、触发动作、这是交互前/中/后哪个状态，以及它证明了什么。

```markdown
![桌面端｜指针交互中｜遮罩扩散到标题右侧](../screenshots/NN-name/desktop-active.png)
[查看 8 秒指针与滚动交互录屏](../recordings/NN-name-interaction.mp4)
```

说明录屏的完整操作顺序与可见变化。静态 Section 没有录屏时，填写明确的中文省略原因。

## WebGL、3D 与 Shader 实现

记录 renderer、camera、scene、geometry、material、light、render target、postprocess、DPR、resize、dispose；Shader 需说明 pass 顺序、uniform、纹理、坐标系、混合计算与反馈帧。无相关技术时写 `N/A — 中文原因`。

## 资源清单

| 资源 | 原始公开 URL | 本地路径 | 用途 | 哈希/解码依赖 | 授权/回退 |
|---|---|---|---|---|---|

## 实现方法与组件职责

用组件树、状态流和一段足够让 Agent 开始编码的伪代码/接口/关键实现片段说明如何完成，不要只写库名。

```text
输入 → 状态 → 布局/动画 → DOM/WebGL 渲染 → 清理
```

## 从空项目复刻步骤

从依赖安装开始给出有顺序的执行步骤，覆盖静态结构、视觉参数、动效、3D/Shader、响应式、降级和测试。

## 验收标准

指定 1440×900 与 390×844 等视口、关键滚动位置、指针/触摸路径、预期截图状态、控制台/网络结果、生命周期动作和视觉容差。

## 证据与可信度

逐条链接证据 ID，使用 `source-confirmed`、`observed`、`inferred` 或 `unknown`，并解释推断边界。

## 已知差异与待确认项

列出无法确认的源实现、缺失资源、等价实现差异，以及复刻 Agent 需要人工判断的内容。
