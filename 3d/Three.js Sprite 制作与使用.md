# Three.js Sprite 制作与使用

## Sprite 是什么

Sprite 是放置在 3D 空间中的二维矩形贴片。它有三维坐标、尺寸和深度关系，但会自动保持正面朝向相机，因此也被称为 Billboard（广告牌）。

常见用途包括：

- 云雾和烟尘
- 光晕、火焰和闪光
- 远景树木
- 粒子贴片
- 3D 标记和图标

Sprite 的几何形状仍然是矩形。使用带透明通道的图片后，图片背景不可见，最终只显示云雾等不规则图形。

## 一般在哪里制作

Sprite 对象通常不是在 Blender 中直接制作，而是由 Three.js 在网页运行时创建。需要提前制作的主要是 Sprite 使用的透明贴图。

贴图可以通过以下工具制作：

- Photoshop：绘制或处理透明云雾图片。
- Blender：渲染烟雾、云或其他三维效果，并输出透明图片。
- Houdini：生成程序化烟雾或粒子素材。
- 生成式图像工具：生成素材后进一步清理透明背景。

常见输出格式包括透明 PNG、WebP 或适合 GPU 使用的压缩纹理。

## Three.js 基础实现

```js
const texture = textureLoader.load('/cloud.png')

const material = new THREE.SpriteMaterial({
  map: texture,
  transparent: true,
  depthWrite: false,
  opacity: 0.5,
})

const cloud = new THREE.Sprite(material)

cloud.position.set(-2, 1, -5)
cloud.scale.set(8, 3, 1)

scene.add(cloud)
```

关键参数：

- `map`：Sprite 使用的图片纹理。
- `transparent`：启用透明通道。
- `depthWrite: false`：避免多个半透明 Sprite 相互遮挡时产生明显的深度写入问题。
- `opacity`：控制整体透明度。
- `position`：设置 Sprite 在三维空间中的位置。
- `scale`：设置可见尺寸和宽高比例。

## 添加漂移动画

```js
function update(elapsedTime) {
  cloud.position.x += 0.0005
  cloud.position.y += Math.sin(elapsedTime * 0.2) * 0.0007
  cloud.material.rotation += 0.00004
}
```

可以通过非常缓慢的位置变化、旋转和透明度变化制造漂浮感。动画幅度过大时，Sprite 的二维贴片感会更容易暴露。

## Blender 可以参与什么

Blender 主要可以承担两个环节：

1. 制作或渲染云雾素材，再导出带透明通道的图片。
2. 使用普通平面预览云雾在场景中的位置、尺寸和构图。

需要注意，GLB 中的普通平面通常不会自动变成 Three.js Sprite。Sprite 始终朝向相机的行为一般由网页运行时代码实现。

## 当前 Hero Demo 的实现流程

```text
6 张原网站云纹理
        ↓
运行时创建 25 个 Sprite
        ↓
随机设置位置、大小、旋转和透明度
        ↓
每帧进行轻微漂移和旋转
```

当前 Demo 还生成了 2000 个 `Points` 粒子作为空气中的灰尘亮点。Sprite 云雾和 Points 粒子共同组成独立于 GLB 模型的氛围层。

原网站使用了更复杂的实例化 Shader 和噪声形变，而当前 Demo 使用 Sprite 实现便于理解和调试的简化版本。
