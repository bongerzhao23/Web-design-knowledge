# FOV 与网页 3D 场景的响应式适配

## FOV 是什么

FOV（Field of View）是透视相机的视野角度。Three.js 中 `PerspectiveCamera.fov` 默认表示**垂直方向的视野角度**。

- FOV 越小：视野越窄，主体看起来越大，类似长焦镜头。
- FOV 越大：视野越宽，主体看起来越小，类似广角镜头。
- 改变 FOV 不等于移动相机。增大 FOV 虽然视觉上像相机退远，但相机位置可以完全不变。

## FOV 如何确定

FOV 首先是一个构图选择，而不是根据网页宽度自动计算的数值。

常见流程：

1. 选择主要设计尺寸，例如 `1440 × 900`。
2. 在 Blender 中调整相机位置、朝向和 FOV，完成理想构图。
3. 将相机随 GLB 一起导出。
4. 网站加载 GLB 后保留这个垂直 FOV。
5. 浏览器尺寸改变时，实时更新相机的宽高比。

这个项目的原始 GLB 相机 FOV 约为 `22.9°`。它决定了花朵、窗户和前景雕塑的基础构图。当前 Demo 可能为了对比实验临时覆盖这个数值。

## 基础响应式实现

```js
camera.fov = 22.9
camera.aspect = width / height
camera.updateProjectionMatrix()
```

三个步骤分别表示：

- `camera.fov`：固定垂直方向能看到的范围。
- `camera.aspect`：使用当前画布的宽高比。
- `updateProjectionMatrix()`：参数变化后重新计算投影矩阵。

当垂直 FOV 固定时：

- 屏幕越宽，垂直范围不变，左右看到的内容更多。
- 屏幕越窄，垂直范围不变，左右看到的内容更少。

因此，基础响应式主要由 `aspect` 完成；FOV 负责镜头气质和基础构图。

## 垂直 FOV 与水平 FOV

水平视角会随着画面宽高比变化，可以用下面的公式计算：

```text
horizontalFov = 2 × atan(tan(verticalFov / 2) × aspect)
```

以垂直 FOV `22.9°` 为例：

| 画面比例 | 水平视角（约） |
| --- | ---: |
| 16:9 | 39.6° |
| 4:3 | 30.2° |
| 9:16 | 13.0° |

这解释了为什么同一个相机在宽屏上能看到更多左右内容，而在竖屏上会发生明显的水平裁切。

## 桌面端与移动端

单靠一个固定 FOV，通常无法让所有宽高比保持完全相同的构图。桌面端与移动端差异较大时，可以为移动端额外调整：

- 相机位置
- 相机 FOV
- 相机观察目标
- 模型整体位置或缩放
- 前景物体的独立位置

实际项目中通常先保持垂直 FOV 和相机机位，在不同尺寸下检查关键主体是否仍在安全区域；只有构图明显失效时，才增加断点参数。

## 本项目中的对应代码

当前 Demo 在窗口变化时使用画布尺寸更新相机：

```js
const width = host.clientWidth
const height = host.clientHeight

camera.aspect = width / height
camera.updateProjectionMatrix()
```

原始构图来自 GLB 内置的 Blender 相机，网页端负责根据画布尺寸更新宽高比，并叠加少量指针视差。
