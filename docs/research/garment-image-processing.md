# 真实服装照片：抠图、穿着分割与正面展示图

核查日期：2026-10-22。目标：先在 Windows 本机完成图片处理闭环，再考虑迁移到无 GPU 的飞牛 OS；每位用户独立管理衣橱。

本文核查了官方 GitHub README、推理源码、发布文件元数据与模型卡。**没有安装模型、下载权重或完成本机/NAS 推理测试。** 文件体积不是运行内存，GPU 论文速度不是 CPU 速度。以下模块和字段均为建议，当前应用尚未实现。

## 推荐结论

1. **平铺/悬挂单件衣服**：用 rembg 的 CPU 后端，比较 `u2netp`（轻量基线）与 `birefnet-general-lite`（质量候选），经真实照片测试后选默认模型。无需训练，也不需要为图像推理引入 WSL。
2. **穿在人身上的衣服**：用 `u2net_cloth_seg` 提取上装/下装/连体服；存在外套与内搭重叠、多人或同类多件时，后续加入 MobileSAM 点/框辅助选择和手工修边。普通去背景不能替代服装分割。
3. **统一衣橱展示**：从真实分割图裁边、按比例缩放、人工旋转/必要的受约束校正、透明画布居中。界面称“整理展示图”，不承诺恢复被遮挡的衣服形状。
4. **穿着照重建平铺商品图**：确实有 TryOffDiff、TEMU-VTOFF 等公开模型，但它们是扩散模型方案，不属于适合当前无 GPU 版本的小模型。作为后续独立 GPU/外部生成任务评估，结果标记为“AI 生成展示图”。

## 三种目标必须分开

| 目标 | 算法输出 | 能保留/推断什么 | 无 GPU 起步建议 |
| --- | --- | --- | --- |
| 去背景 | 前景 mask/alpha + 原照片颜色 | 已拍到的可见衣物；可能残留床单/阴影 | 立即进入本机验证 |
| 穿着衣物分割 | 指定衣物类别/区域的 mask | 可见布料，仍保留人体造成的褶皱和形状 | 第二步；允许人工修正 |
| 正面/平铺重建 | 重新生成标准视角的图片 | 不可见部分由模型推断，花纹/文字/纽扣/剪裁可能改变 | 独立可选功能，不能覆盖原图 |

单张照片看不到被手臂、头发、外套遮住的布料，也不包含衣服背面的证据。生成结果可以适合视觉陈列，却不能据此确认材质、准确尺寸或隐藏图案。

## 本地抠图候选（按仓库 Stars 降序）

Stars 为本次 GitHub REST API 实时读取的快照，只覆盖筛选的候选。rembg 是推理封装，不是一个新模型；同一行中的权重不能由封装代码的许可证代替其自身许可。

| 仓库 | Stars | 选用内容与文件规模 | CPU 和适用范围 | 许可/状态 |
| --- | ---: | --- | --- | --- |
| [danielgatis/rembg](https://github.com/danielgatis/rembg) | 25,156 | `rembg[cpu]`，复用已加载 session | 官方支持 CPU；可统一加载下面的 ONNX 模型 | 封装 MIT；权重单独核查 |
| [xuebinqin/U-2-Net](https://github.com/xuebinqin/U-2-Net) | 9,883 | rembg `u2netp` ONNX **4.57 MB**；完整 `u2net` **176.00 MB** | 320×320 模型输入；单件平铺抠图基线 | 源码 Apache-2.0；ONNX 由 rembg 发布，记录转换来源 |
| [ChaoningZhang/MobileSAM](https://github.com/ChaoningZhang/MobileSAM) | 5,894 | 官方 `mobile_sam.pt` **40.73 MB** | 点/框引导分割，适合用户纠错；官方展示 CPU demo | 仓库 Apache-2.0；不是自动衣物类别识别器 |
| [ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | 4,318 | rembg `birefnet-general-lite` ONNX **224.01 MB** | 高分辨率分割质量候选，CPU 延迟/内存必须实测 | 源码 MIT；官方 Lite 模型卡 MIT |
| [levindabhi/cloth-segmentation](https://github.com/levindabhi/cloth-segmentation) | 672 | rembg `u2net_cloth_seg` ONNX **176.19 MB**，768×768 输入 | 穿着照分为上装/下装/连体服，不能分清所有同类实例 | 仓库 MIT；已归档，保留源自 U²-Net 的许可及权重来源 |

文件规模统一按十进制 MB；直接来自 [rembg release API](https://api.github.com/repos/danielgatis/rembg/releases/tags/v0.0.0) 和 [MobileSAM 文件 API](https://api.github.com/repos/ChaoningZhang/MobileSAM/contents/weights/mobile_sam.pt)，未实际下载。BiRefNet 的不同 HF/ONNX 导出体积不同，不能把 224 MB 推广到全部 Lite checkpoint。

### 选择时容易踩的坑

- **显式指定模型。** 本次 [rembg session_factory.py](https://github.com/danielgatis/rembg/blob/main/rembg/session_factory.py) 的默认值是 `bria-rmbg`。它对应的 BRIA 权重并不因 rembg 为 MIT 就变成 MIT；[官方模型说明](https://huggingface.co/briaai/RMBG-2.0) 与 rembg 文档提示商业使用需另行许可。我们的第一版无需默认下载它。
- **轻量不等于服装专用。** [U²-Netp session](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2netp.py) 以 320×320 推理后上采样 mask。细绳、蕾丝、镂空及与床单同色的衣服是必要评测项；不能用上采样宣称已恢复细节。
- **穿着类别必须传入。** [服装 session](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2net_cloth_seg.py) 支持 `cloth_category="upper" / "lower" / "full"`；不指定会返回多个类别 mask。外套与内搭属于同一上装类别时，不应声称已自动分成两件。
- **MobileSAM 的 ONNX 导出不能直接当成完整纯 ONNX 管线。** [官方导出脚本](https://github.com/ChaoningZhang/MobileSAM/blob/master/scripts/export_onnx_model.py) 接收 `image_embeddings`，导出提示编码器和 mask decoder；图像 encoder 仍须运行或另行导出验证。官方 Mac i5 CPU demo 的约 3 秒只是作者环境结果，不是本机或 NAS 承诺。
- **BiRefNet Lite 值得比较，但不预先判定最佳。** [官方 Lite 模型卡](https://huggingface.co/ZhengPeng7/BiRefNet_lite) 与 [rembg Lite session](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/birefnet_general_lite.py) 给出来源与加载方式；是否比 U²-Netp 更适合本项目，应由衣服样本质量与峰值内存决定。
- 服装分割并不等于透明材质的精确抠像。轻微边缘羽化或 alpha matting 可以改善部分边缘，但无法保证恢复透明纱布的真实透射颜色；先保留原图供对照。

## “正面无畸变”如何分步实现

### 可做的确定性处理

```text
原照片 → EXIF 方向校正 → 选取目标衣物 → mask/alpha
       → 保留可见布料生成透明图 → 裁边/旋转/等比例缩放
       → 固定透明画布 → 用户对照确认
```

- 平铺拍摄时，衣服展开、镜头尽量正对衣服、背景与衣服颜色区分开、减少硬阴影，比后处理强行拉正更可靠。
- 边界框和轮廓用于裁剪与居中；衣服长轴只适合给出旋转建议，不能自动判定领口方向。鞋/围巾/不对称服装尤其不应强制拉成模板。
- [OpenCV 单应性文档](https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html) 的透视校正建立在近似共面点对应关系上。可用于有可靠平面参照的斜拍校正；不能仅凭衣服外接矩形恢复真实比例，更不能消除人体曲面、褶皱或遮挡。
- 镜头径向畸变需要相机标定/已知参数；旋转与四点透视变换并不自动解决所有镜头畸变。
- 不默认强行对称、不补齐缺袖、不抹平纹理。只做可解释的几何整理时仍标为真实照片处理结果；补画内容则归入生成展示图。

### 真正的正面重建

可见衣物作为条件，生成模型预测平铺轮廓与不可见内容，随后再去背景；其输入输出方向应是“人像 → 服装图”。IDM-VTON、CatVTON、CatV2TON 的主要方向为“服装 → 人像试穿”，不能直接替代这个模块。下文列出本次核实的反向方案。


## 穿着照：先提取可见衣服，再决定是否生成补全

穿着图中的背景、皮肤、头发、裤子、上衣需要分别识别。通用前景抠图可能把整个人保留下来；衣服语义分割输出的是可见区域，不会恢复被手臂挡住的图案或衣服背面。建议 UI 先选“上衣 / 下装 / 连衣裙”，再让用户确认或修正蒙版。

### SegFormer B2 clothes：有可部署权重，但许可限制明显

- 作者训练仓库是 [mattmdjaga/segformer_b2_clothes](https://github.com/mattmdjaga/segformer_b2_clothes)，基于 ATR 人体解析数据训练。GitHub 训练代码为 [MIT](https://github.com/mattmdjaga/segformer_b2_clothes/blob/main/LICENSE)。
- [作者模型卡](https://huggingface.co/mattmdjaga/segformer_b2_clothes)标注 27.4M 参数，18 类包括 upper-clothes、pants、skirt、dress、左右鞋、bag、scarf，以及皮肤/头发等人体区域。上衣统一为一类，没有单独 jacket/shirt 类，因此无法仅靠类别将外套和内搭稳定分成两个衣物实例；同类多件也需要裁剪、交互选择或实例分割补充。
- [权重目录](https://huggingface.co/mattmdjaga/segformer_b2_clothes/tree/main)的 safetensors 约 109 MB；[同一作者仓库内 ONNX 目录](https://huggingface.co/mattmdjaga/segformer_b2_clothes/tree/main/onnx)提供约 110 MB 的 model.onnx 和预处理配置。可作为 ONNX Runtime CPU 验证候选，但尚未在本项目验证导出兼容性和速度。
- **权重不是可以直接按 MIT 使用。** 模型卡 license 为 `other`，License 段链接到 [NVIDIA SegFormer License](https://github.com/NVlabs/SegFormer/blob/master/LICENSE)，其中 non-commercially 定义为 research/evaluation。适合先作算法评估；要作为日常使用或公开发布的默认组件，应先明确权重使用授权。
- 可在模型卡看到按类别 IoU 差异较大；数据集评测不能当作用户真实照片的质量保证。这里不把它推荐为未经比较的最终默认模型。

## 真正的反向试衣：穿着照生成商品式正面图

以下方案有与本需求方向相符的代码和权重，任务通常叫 Virtual Try-Off / inverse virtual try-on。它们通过生成补全遮挡区域，不是像素保真的“还原”。是否保留文字、纽扣数量、袖长和版型，必须以成对真实照片验证。

GitHub star 为当日 API 快照，仅作社区规模参考；按 star 降序列出。下载体积均不代表完整运行环境或 RAM/VRAM。

| 项目 | Stars | 已发布能力及体积证据 | 硬件及许可结论 |
|---|---:|---|---|
| [catvton-flux / cat-tryoff-flux](https://github.com/nftblackmagic/catvton-flux) | 613 | 提供 `tryoff_inference.py`，输入穿着照和 mask，输出正面商品衣物；[try-off 权重约 23.8 GB](https://huggingface.co/xiaozaa/cat-tryoff-flux/tree/main) | 作者 README 要求 VRAM ≥40 GB。代码 MIT；权重卡标 CC BY-NC 2.0，README 另要求遵守 FLUX Fill / VITON-HD 条款。明显不适合 CPU NAS。 |
| [Any2AnyTryon](https://github.com/logn-2024/Any2anyTryon) | 167 | 有单独 garment reconstruction LoRA，约 [598 MB](https://huggingface.co/loooooong/Any2anyTryon/tree/main)；代码提供穿着图→平铺图提示词 | **598 MB 仅适配权重**，还需 [FLUX.1-dev 12B](https://huggingface.co/black-forest-labs/FLUX.1-dev) 基座及编码器。`app.py` 显式 CUDA。仓库根目录没有 LICENSE，权重仓库没有模型卡许可；基座为 FLUX dev 非商业许可证。暂不作为集成首选。 |
| [TryOffDiff / MGT](https://github.com/rizavelioglu/tryoffdiff) | 152 | v1 上衣，v2 支持上衣/下装/连衣裙及统一多类模型；[v2 单权重约 3.44 GB](https://huggingface.co/rizavelioglu/tryoffdiff/tree/main)，还需 VAE、SigLIP 等 | 基于 SD1.4，规模比 FLUX 方案更适合后续 GPU 实验。源码与权重为 SSPL，README 声明研究用途。没有本次核实到的 CPU 实测指标；v2 源码硬编码 CUDA，不能称为开箱 CPU 部署。 |
| [TEMU-VTOFF](https://github.com/davidelobba/TEMU-VTOFF) | 52 | 明确针对多类穿着照→商品图；[模型库约 8.09 GB](https://huggingface.co/davidelobba/TEMU-VTOFF/tree/main)，只有双 DiT 模块，仍需 SD3 编码器/VAE与视觉编码器 | 代码和权重 CC BY-NC 4.0；另有 SD3 基座访问和许可要求。推理代码包含 CPU fallback，但没有本次核实到的 CPU 性能证据；不建议作为无 GPU NAS 默认流程。 |

### TryOffDiff 是较值得保留的 GPU 实验候选

[官方 README](https://github.com/rizavelioglu/tryoffdiff/blob/main/README.md)说明基座为 Stable Diffusion 1.4、视觉编码器为 SigLIP；[模型卡](https://huggingface.co/rizavelioglu/tryoffdiff)列出单类和多类权重。不要把所有权重总计 17.2 GB 当作单次运行必须下载体积：单一 v2 checkpoint 约 3.44 GB，但还要补齐其依赖模型。

[推理配置](https://github.com/rizavelioglu/tryoffdiff/blob/main/tryoffdiff/config.py)虽允许 `cpu`，[v2 模型构造器](https://github.com/rizavelioglu/tryoffdiff/blob/main/tryoffdiff/modeling/model.py#L43)仍将 SigLIP 设为 `device_map="cuda"`。这意味着 CPU 部署至少需要源码适配与运行验证；不能仅依据命令行参数声称支持。官方 [v2 推理说明](https://github.com/rizavelioglu/tryoffdiff/blob/main/references/v2_instructions.md)示例使用 20 步，这也不是单次轻量分割的计算量。

[LICENSE](https://github.com/rizavelioglu/tryoffdiff/blob/main/LICENSE)为 SSPL，包含提供公共服务时的源代码义务；README 另有 academic research 描述。现阶段只建议隔离评估，公开服务或再分发前核清许可，不把其与 MIT/Apache 模型等同。

### TEMU-VTOFF 的“单图推理”还有额外输入

[inference.py](https://github.com/davidelobba/TEMU-VTOFF/blob/main/inference.py)不仅读取原照片，还读取同目录的 `_caption.txt`、`_fine_mask.jpg` 和 `_binary_mask.jpg`。因此本项目接入需要先完成目标衣物蒙版与描述，不能直接将上传原图交给它便声称整条链路完成。该文件加载双 DiT、三个文本编码器、VAE，以及 CLIP-Large 和 CLIP-bigG，进一步说明它不是小型 CPU 算法。

[作者模型卡](https://huggingface.co/davidelobba/TEMU-VTOFF)明确说明上传的是 feature extractor 与 VTOFF DiT；其网页展示的参数摘要不能替代整条管线的内存评估。代码有 CUDA 不可用时的 CPU 分支，只能证明作者写了该分支，不能证明 NAS 运行速度可接受。

### 需要排除或区分的名称

- [CatV2TON](https://github.com/Zheng-Chong/CatV2TON)主要是图像/视频正向试衣，不能当作现成的衣物正面提取器。与它名称接近的 `nftblackmagic/catvton-flux` **确实另外发布了 try-off 模型**，两者必须区分。
- 本轮对 `GarmentExtractor` 的 GitHub/模型库精确搜索未找到足以确认代码、权重、许可的同名官方项目，因此不把这个名字列为已验证可部署方案；这不证明不存在其他同名实现。
- LoRA 文件较小不代表完整模型较小，CPU offload 也通常是 GPU 推理时将部分模型换入/换出内存，不能据此认定完全无需 GPU。Any2AnyTryon 的 [app.py](https://github.com/logn-2024/Any2anyTryon/blob/main/app.py)仍明确创建 CUDA 设备并转移管线到该设备。

## 接入当前 IWardrobe 的最小方案

已读取当前源码：`backend/src/iwardrobe/media.py` 只做图片检查、私有保存与缩略图；`jobs.py` 只调度 `process_thumbnail`。现有架构足够承接 CPU 推理，不需要换框架。

### 文件落点（建议，尚未修改）

```text
backend/src/iwardrobe/
  image_processing.py       新增：分割、mask、透明图与画布整理
  media.py                  复用：私有路径、EXIF、文件写入
  jobs.py                   扩展：cutout 任务与按 kind 分发
  models.py                 扩展：mask/抠图/预览路径与模型元数据
  schemas.py / main.py       扩展：处理请求、结果选择、私有图片读取
backend/migrations/versions/
  <new_image_fields>.py      对应数据迁移
apps/web/src/features/
  capture/AddGarment.tsx     平铺/穿着选择、目标衣物类别
  wardrobe/GarmentDetail.tsx 原图/处理图对照、采纳、重试
  jobs/JobsPanel.tsx         复用异步状态展示
scripts/
  benchmark-cutout.py        后续实测脚本，非产品运行依赖
```

第一步只新增一个处理模块，用简单的 `extract_garment(image, mode, category)` 接口封装推理及后处理，返回透明图、mask、模型版本等元数据。session 在 worker 初始化时加载/复用；不在每张照片或 HTTP 请求里重新加载，不先做通用 AI 插件框架。所用模型和 ONNX Runtime 版本锁定，权重在独立缓存目录保存校验值，不加入源码仓库。

第一版可以在现有 Asset 上添加 `mask_key`、`cutout_key`、`processed_preview_key` 和处理元数据，继续保留 `original_key` 与原来的缩略图。后续真正引入多版本生成时再考虑派生图片表，避免现在修改“一件衣服一个 Asset”的所有逻辑。

```text
上传并保存原图
  ├─ 原有缩略图任务 → 立即可浏览
  └─ cutout 任务 → 待确认处理结果 → 用户采纳为展示图
                                      ↓
                         之后可单独请求 generated_display
```

- 处理状态与用户采纳分开：推理成功不代表结果正确。用户应能回看原图、保留当前展示、重试。
- 每个派生文件继承原图的 user_id/asset_id 权限，继续经现有私有图片路由读取；模型不需要跨用户共享照片。
- `reconcile()` 当前把所有任务都投给 `process_thumbnail`，接入时必须按 `Job.kind` 分发。
- 当前 worker 为 `max_jobs=1`、`job_timeout=60`，租约为 90 秒。CPU 推理测试后再确定超时，并同步设计租约续期/期限；不能只增加超时而导致 90 秒后任务被重复领取。
- 从单任务并发起步，控制 ONNX 线程数。耗时推理不阻塞 Web 请求；如果要强制取消超时计算，应使用可终止的独立推理进程，因为取消 `asyncio.to_thread` 不会停止底层 ONNX 计算。
- 继续采用临时文件加原子发布、dispatch_key 复核、失败保留原图。数据库提交时确认用户、Asset 和当前任务仍有效。
- 图像推理可直接运行在 Windows Python 3.12；[rembg 当前声明支持 Python >=3.11,<3.14](https://github.com/danielgatis/rembg#requirements)。这是依赖兼容范围证据，不是已安装通过的结果。

## 实施与验收顺序

1. **离线比较**：取 20–30 张授权真实照片，覆盖平铺/悬挂/穿着、浅色同色背景、深色衣服、条纹印花、细肩带、镂空、手臂遮挡。先跑 U²-Netp 与 BiRefNet Lite，再比较服装分割。现有透明生图 fixture 只适合验证入库和显示，不能代表真实抠图能力。
2. **记录结果**：区分首次加载和热推理耗时，测 P50/P95、峰值进程内存、失败数；人工逐张对比漏衣服、残留人体/背景、细节、颜色、纹理。对小部分图标注 mask 可算 IoU/边缘指标，但不能用高 IoU 掩盖细肩带丢失。
3. **本机闭环**：上传→排队→分割→对照→采纳→刷新/重启后仍可访问。验证跨用户不可读、失败重试不覆盖原图、处理期间删除/失效不会发布旧结果。
4. **必要时加修正**：先提供旋转、裁剪、画笔恢复/擦除，再按真实失败样本决定是否值得接 MobileSAM。
5. **单独评估生成**：仅当真实分割与整理不能满足陈列需要时，比较反向模型/外部 GPU 推理；逐一审核文字、花纹、口袋、纽扣与轮廓。生成图始终保留来源和用户确认。
6. **最后迁移 NAS**：使用相同样本、模型与参数测飞牛机器。CPU 架构与内存尚未给出，当前不承诺 NAS 每张耗时或支持并发数。

本次交付为有来源的选型与接入建议；没有更改应用运行代码，没有运行模型基准，也没有提交或推送 Git。
