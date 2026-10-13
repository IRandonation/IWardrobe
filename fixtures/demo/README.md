# 生成的衣橱测试图片

2026-10-13 使用 Codex 内置 `image_gen` 工具（`imagegen` 技能的内置工具模式）生成，未调用项目内 API、未使用真实用户照片。

| 文件 | 内容 |
| --- | --- |
| `images/oat-knit.png` | 燕麦色圆领针织衫 |
| `images/navy-shirt.png` | 藏蓝色工装衬衫 |
| `images/olive-trousers.png` | 橄榄绿直筒长裤 |
| `images/white-sneakers.png` | 奶白色帆布鞋 |

四张 PNG 都是 1254×1254 的透明背景合成图，已检查 RGBA 通道及透明像素。图片与 `manifest.json` 通过演示导入功能进入每个账号自己的数据库和私有文件目录。`demo_key` 保留来源标记；不把它们当作真实衣物或真实模型识别结果。

这些样本验证上传、显示、缩略图、字段保存和衣橱交互。它们不能验证床面背景分割、人体衣物提取、透视恢复、洗标识别或真实推荐质量。后续要增加获授权的真实照片评估集。

## 提示词

每张图片使用以下公共模板，将 `{subject}` 替换为表中的完整文本。参数为 `transparent_background: true`，没有引用输入图片。

```text
Use case: product-mockup. Asset type: synthetic wardrobe test photo for a private wardrobe app. Subject: {subject} Photorealistic e-commerce garment photography. Centered object on a genuinely transparent background, square composition with generous 12 percent margins. Soft diffuse neutral light, realistic fabric texture, clean silhouette. No human, no mannequin, no hanger, no labels, no text, no watermark, no brands. Do not include other objects. This is synthetic demo data.
```

| 文件 | subject |
| --- | --- |
| oat-knit.png | One oatmeal beige ribbed crewneck long sleeve sweater, fine cotton knit, neatly laid flat, sleeves slightly angled down. |
| navy-shirt.png | One navy blue long sleeve cotton overshirt with two chest pockets and dark buttons, neatly laid flat, sleeves slightly angled down. |
| olive-trousers.png | One pair of muted olive green straight leg cotton trousers, neatly laid flat, waistband at top, both full length legs visible. |
| white-sneakers.png | One pair of off-white low-top minimalist canvas sneakers, no logo, arranged symmetrically three-quarter top view, complete shoes visible. |
