---
name: web-design-radar
description: Use when 用户要求分析获奖或高技术网站首页（Awwwards 等）、section-by-section 拆解前端实现、保存 3D/WebGL/Shader/字体等 1:1 复刻资源，或执行每日 2 站的 daily batch 研究任务；这是此类任务的首选，取代旧 awwwards-crawler。无头 Playwright Chromium 负责截图、资源和证据，用户的 Mac 在线时用 Ego Lite 高帧率录屏。
---

# Web Design Radar（网页设计雷达）

目标：为一个公开网站首页产出可长期复用的案例包，让后续 Agent 能据此 1:1 复刻，同时不把推测写成已确认的源码事实。

下文的 `$KIT` 指本 `SKILL.md` 所在目录。所有命令都在 `$KIT` 下执行。状态和成品默认放在 `~/Desktop/Web Design Radar/`；没有 `~/Desktop` 的机器（比如 Linux 服务器）放在 `$KIT/archive/`；设置环境变量 `WEB_DESIGN_RADAR_ROOT` 可以改到别处。

## 何时使用

- 用户给出一个网站 URL，要求分析设计、动效、3D、前端技术，逐 Section 解释，或者“帮我拆解/复刻这个网站”。
- 用户要求从 Awwwards 等榜单挑站研究（每日 2 站的 daily batch 模式）。
- 不适用：需要登录、验证码、付费墙后的页面；只想要一句话审美点评的，直接回答即可。

## 首次准备（只需一次）

```bash
cd $KIT && ./setup.sh        # venv + Playwright + 自带的无头 Chromium，缺 ffmpeg 时用 apt 安装（Linux）
./run_tests.sh               # 自检，应全部 OK
./wdr init --json            # 初始化 archive
```

`setup.sh` 按 Linux 写的。在 Mac 上用 brew 装 ffmpeg，其余几步照做即可。

## one-off 单站模式（主流程）

1. 建立或恢复运行：
   `./wdr start-one-off --url <站点URL> --source-url <来源页，如 Awwwards 页面或站点本身> --json`，记下 `runId` 和 `stagingDir`。同一天同一站点已经完成又要重做，加 `--rerun`（会生成 `-r2` 这样的新运行）。
2. 每个阶段先领取：`./wdr claim-stage --slot M --owner <名字> --json`。做完后写一个结果 JSON（如 `{"status":"ok","browserUsed":"playwright-chromium"}`），再
   `./wdr submit-stage --run-id <RUN_ID> --stage <阶段> --owner <名字> --result <结果JSON绝对路径> --json`。
   阶段顺序固定：`observing → extracting → assets → documenting → validating`。失败时用 `fail-stage`。
3. observing（采集）：先读 `references/browser-acceptance.md`，然后运行
   `capture/run.sh --url <站点URL> --staging <stagingDir> --max-sections 6 --cache-assets`（约 5 分钟；加 `--fast` 约 3 分钟：等待更短、每 3 屏一张逐屏图、录屏 7 秒）。
   其他参数：`--video-seconds N`（6–12）、`--record-width 1280`（录屏输出宽度，视口仍是 1440×900）、`--no-video`、`--no-media-download`、`--media-cap-mb 60`。
   脚本会自动处理这些事：关掉 Cookie/同意弹窗（常见 CMP 和多语言“接受/同意”按钮，包括 iframe 里的；从不点登录或订阅，点不掉就用 CSS 隐藏）；桌面和移动端并行采集；按全宽 DOM 区块切分 Section，移动端定位同一个 DOM 元素截图；之后单独用 Playwright 原生录屏，按真实时间平滑滚动录每个 Section；做缩放（桌面→移动→桌面）、离开/返回、刷新三项生命周期检查；无头浏览器中断的视频用普通请求直接下载（有大小上限）。
   产出：截图、`recordings/NN-desktop-scroll.mp4`、`screenshots/_global/lifecycle/`、`evidence/capture-summary.json`（consent、录屏帧率、lifecycle、mediaDownloads、资源、库、错误、耗时）、`evidence/section-index.draft.json`。原始 HTML/CSS 和资源缓存在 `<stagingDir>/../raw-analysis/`，不进成品。
   自动切分只是草稿。亲自看一遍截图，修正 Section 划分和中文命名，再写正式的 `evidence/section-index.json`。如果 `accessWallSuspected` 为 true，停下并报告。
4. extracting（提取）：读 `references/evidence-contract.md`。分析 raw-analysis 里的 HTML/CSS 和采集摘要，写 `evidence/EV-<n>.json` 和 `evidence/claims.json`。每条结论标注 `source-confirmed` / `observed` / `inferred` / `unknown` 并关联证据；检测到某个库只代表“存在”。
5. assets（资源）：读 `references/asset-policy.md`。已下载的视频可以用 `capture/record_cached.py --run-id <RUN_ID> --staging <stagingDir> --kinds video --used-by <sections/NN-名.md> --limit 1` 批量登记；其他需要的公开资源用
   `./wdr record-asset --run-id <RUN_ID> --source-url <URL> --input-file <raw-analysis/asset-cache/文件> --local-path assets/<类别>/<名> --mime <类型> --used-by <sections/NN-名.md> --json`。许可证不明时记 `unknown`。
6. documenting（写文档）：读 `references/section-contract.md`，用 `templates/overview.md` 写唯一的 `00-网站整体前端技术总结.md`（≥1200 非空白字符、≥200 汉字），用 `templates/section.md` 给每个真实 Section 写 `sections/NN-中文名称.md`（≥900 字符、≥120 汉字、含代码块，覆盖全部必备小节，逐张嵌入截图并链接录屏）。
7. validating（验证）：`./wdr validate-case --revision <stagingDir> --json`，修到 `passed: true` 再提交这个阶段。
8. 发布：`./wdr finalize-one-off --run-id <RUN_ID> --json`，返回 `published: true` 才算完成，成品在返回的 `outputPath`。

## 录屏后端：默认 mac-ego，无头录屏作后备

- 默认：如果能在用户的 Mac 上执行命令，而且 Mac 装了 Ego Lite（`ego-browser` CLI），Section 录屏放到 Mac 的 GPU 上录（M2 Pro 实测 75–99 fps）。采集机器仍然负责截图、资源、证据和 Section 切分，可以加 `--no-video` 省时间。
- 后备：Mac 不在线、用户没批准 Mac 上的命令、或者 mac-ego 失败时，用 `capture/run.sh` 自带的无头录屏（没有 GPU 的机器上大约 7–16 fps，文档里注明 effectiveFps）。

### mac-ego 步骤

1. 采集机器：`python3 capture/mac/make_targets.py --staging <stagingDir> --run-name <名称> --seconds 8 --consent hide`，得到目标 JSON（每个 Section 的起止滚动位置；无头那边没录屏时按 `section-index.draft.json` 推算）。
2. Mac 上合并成一条命令执行：用 heredoc 把 `capture/mac/ego_record.mjs` 写到 `~/web-design-radar-mac/ego_record.mjs`，目标 JSON 写到 `~/web-design-radar-mac/targets.json`；后台运行 `~/.local/bin/ego-browser nodejs < ~/web-design-radar-mac/ego_record.mjs > ~/web-design-radar-mac/record.log 2>&1`，用 PID 循环最多等 300 秒（macOS 没有 `timeout`），再打印日志。ego-browser 不转发环境变量，所以脚本固定读 `~/web-design-radar-mac/targets.json`。
   - 先读 Mac 上的 ego-browser Skill（`~/.agents/skills/ego-browser/SKILL.md`）并照做：只用一个 Agent 自己的 TaskSpace，不碰用户的标签页、登录、cookie 或配置；结束时 `finish({ keep: [] })`。
   - `consent` 默认 `hide`，只用 CSS 隐藏、不点击。TaskSpace 用的是用户自己的 Ego Lite 配置，点一下就会把同意选择存进用户的浏览器。只有用户明确同意才用 `click`。
   - 输出在 `~/web-design-radar-mac/out/<名称>/`：`recordings/NN-desktop-scroll.mp4`、`screenshots/`、`mac-record-summary.json`。
3. 把 `mac-record-summary.json` 和 `recordings/*.mp4` 拷回采集机器，放到 `<stagingDir>/mac-import/`（summary 在顶层，MP4 在 `recordings/` 下）。用 Agent 平台的文件拷贝工具或 scp 都行。
4. 采集机器：`python3 capture/mac/import_recordings.py --staging <stagingDir>`，它会替换录屏并把 `captureMethod` 设成 `ego-lite-cdp-screencast`。observing 阶段的结果写 `{"status":"ok","browserUsed":"ego-lite"}`，Section 文档里写明录屏的 effectiveFps 和 Mac GPU。
5. 如果 ego-browser 输出 `[ego-browser:notice]` 更新提示：先结束浏览器任务并告诉用户，用户同意了才运行 `ego-browser upgrade`，升级后重读 ego-browser Skill。

## daily batch 每日批量模式（可选）

按 `prompts/daily-coordinator.md`：用网页搜索在 Awwwards 找 2 个高技术站点，写符合 `contracts/candidate-list.schema.json` 的候选 JSON，`./wdr start-batch --date <日期> --candidates <JSON> --json`，再按 `prompts/site-worker.md` 依次跑 slot A、B，最后 `./wdr finalize-day --date <日期> --json`。09:00（Asia/Shanghai）之后不再开始新的采集。

定时触发由 Agent 自己的例程负责。用 OpenClaw 的话，可以用 `scripts/declare-crons.py` 声明定时任务（创建时为 disabled，启用是单独一步，任务 ID 存在 `state/automation.json`）。

## 不变规则

- 只分析公开页面；不绕过登录、验证码、DRM、付费墙或混淆保护；不保存 cookie、请求头、token。
- 无头采集只用 kit 自带的 Chromium（全新无痕上下文）；Mac 录屏只用 Ego Lite 的 Agent TaskSpace，不接管用户标签页。确实需要别的浏览器时，结果里写 `browserUsed: other-browser`（OpenClaw 环境可写 `openclaw-chrome`）和具体的 `browserFallbackReason`。
- 用户可见正文以中文为主，技术标识和代码可以保留英文；一个 Section 对应一个 Markdown，数量和真实首页一致。
- 每个 Section 至少 4 张不同状态的截图；有交互、动画、滚动联动或 WebGL 的 Section 还要有短视频，并在对应 Markdown 里逐项引用解释。
- 完整的 HTML、CSS、JavaScript 不属于最终交付，只摘录支撑结论的短片段。
- 无论用哪种录屏后端，文档里都注明 `effectiveFps`。
- 宁可交付真实的部分结果，也不要编造完整性。

## 最终回复用户

用中文说明：站点与来源、成品路径（总览文档和 sections 目录）、主要技术结论（含可信度）、几张代表截图或录屏的路径、没能确认的项和原因。
