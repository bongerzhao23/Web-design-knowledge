# 生产级 Three.js 模块 AI 提示词

## 为什么需要明确这些要求

如果只要求 AI“使用 Three.js 实现这个效果”，通常会优先完成可见画面，不一定完整处理工程生命周期、响应式、性能和 GPU 资源释放。

一个可以长期运行在正式网站中的 Three.js 模块，还需要处理：

- 容器尺寸变化
- Retina 屏幕性能
- 页面后台暂停
- 组件重复挂载
- 异步加载竞争
- 资源加载失败
- 事件监听器清理
- GPU 资源释放
- 桌面端与移动端质量分级

## 可直接使用的完整提示词

```text
请使用 Three.js 实现该 3D 效果，并按照能够用于正式网站的生产级方式组织代码。

功能与架构要求：

1. 将 Three.js 场景封装成职责清晰的独立模块或 Scene 类，不要将所有逻辑堆在页面组件中。

2. 提供完整的场景生命周期：
   - init：创建 Scene、Camera、Renderer 和必要资源。
   - start：启动时钟和渲染循环。
   - resize：更新 Renderer 尺寸、Camera aspect 和投影矩阵。
   - pause：页面不可见时暂停时钟和渲染。
   - resume：页面重新可见时安全恢复。
   - dispose：停止渲染并释放全部资源。

3. 使用容器实际尺寸完成响应式适配，优先使用 ResizeObserver，而不是只监听 window.resize。

4. 更新尺寸时必须同步执行：
   - renderer.setSize(width, height, false)
   - camera.aspect = width / height
   - camera.updateProjectionMatrix()

5. 限制 devicePixelRatio，例如最大为 2，兼顾 Retina 屏幕清晰度和 GPU 性能。

6. 使用 requestAnimationFrame 或 renderer.setAnimationLoop 管理渲染，并确保同一场景不会创建多个并行循环。

7. 动画使用 deltaTime，并限制异常过大的 deltaTime，避免页面从后台恢复时动画突然跳跃。

8. 监听 document.visibilitychange：
   - 页面进入后台时暂停 Clock 和渲染。
   - 页面回到前台时重新启动 Clock，避免累计后台时间。

9. 提供资源加载进度、完成状态和失败处理。GLB、纹理或 Shader 加载失败时，应显示明确错误，不要让页面永久停留在加载状态。

10. 处理异步销毁竞争：如果组件在资源加载完成前已经卸载，不得继续向已销毁的场景添加模型或启动渲染循环。

11. 组件卸载或场景关闭时，必须清理：
   - pointermove、resize、visibilitychange 等事件监听器
   - ResizeObserver
   - requestAnimationFrame 或 renderer.setAnimationLoop
   - lil-gui、stats 等调试面板
   - 场景创建的 Canvas DOM

12. dispose 阶段必须释放：
   - BufferGeometry
   - Material
   - Texture
   - WebGLRenderTarget
   - 后处理 Pass
   - Draco、KTX2 等 Loader 持有的资源
   - WebGLRenderer

13. 如果多个 Mesh 共享同一个 Geometry、Material 或 Texture，避免重复 dispose；建议建立统一资源所有权或去重集合。

14. 避免重复创建 Canvas、事件监听器和 WebGL Context。开发环境热更新或组件重复挂载后，页面中仍只能存在一个对应的 Canvas。

15. 对桌面端和移动端分别控制渲染质量，例如：
   - pixelRatio 上限
   - 粒子数量
   - RenderTarget 分辨率
   - 阴影尺寸
   - 后处理开关
   - 抗锯齿策略

16. 不要在每一帧创建新的 Vector、Matrix、Array 或临时对象，尽量复用对象，减少垃圾回收抖动。

17. 对 WebGL Context 丢失提供基本处理或明确的降级状态。

18. 完成后进行以下验证：
   - 多次进入和离开页面后没有新增 Canvas。
   - 不存在重复动画循环或重复事件响应。
   - 切换标签页后能够正常暂停和恢复。
   - 改变浏览器尺寸后画面比例正确，没有拉伸。
   - 桌面端和移动端均可运行。
   - Console 没有错误或资源释放警告。
   - renderer.info 中的 geometry、texture 等资源数量不会在重复挂载后持续增长。

请先说明代码结构，再实现完整代码，并在完成后报告生命周期、响应式、性能和资源释放的验证结果。
```

## Vue 项目补充要求

如果项目使用 Vue 3，可以追加：

```text
这是一个 Vue 3 项目。

请将 Three.js 封装为独立 Scene 类：

- 在 onMounted 中创建实例并调用 start。
- 在 onBeforeUnmount 中调用 dispose。
- Canvas 挂载到组件提供的 ref 容器中。
- 不要把 Scene、Camera、Renderer 等大型可变对象做深度响应式处理。
- 防止组件卸载后异步加载回调继续修改场景。
- 开发环境热更新和路由往返后不得产生重复 Canvas 或 WebGL Context。
```

## React 项目补充要求

如果项目使用 React，可以追加：

```text
这是一个 React 项目。

请在 useEffect 中创建 Three.js 场景实例，并在 cleanup 函数中执行 dispose。

需要兼容 React Strict Mode 的重复挂载检查，确保不会遗留 Canvas、动画循环、事件监听器或 GPU 资源。
```

## 简短版本

如果已经提供了详细效果描述，可以在结尾补充：

```text
请将它实现为生产级 Three.js 模块，而不是一次性视觉 Demo。必须处理完整生命周期、容器响应式、DPR 限制、后台暂停、异步销毁保护、事件清理和全部 GPU 资源释放，并验证重复挂载后不存在 Canvas、渲染循环或显存泄漏。
```
