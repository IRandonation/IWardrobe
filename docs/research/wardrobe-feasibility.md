# 家庭衣橱与每日穿搭：开源候选和技术可行性

核查日期：2026-10-13。用户环境：飞牛 OS NAS，无 GPU；CPU、内存和架构尚未提供。

本文是 GitHub 仓库、部分关键源码及官方模型文档的调研笔记，不是已部署、性能基准或照片识别质量测试。Stars 是本次 GitHub API 读取值；排序范围为筛选后的候选，并非 GitHub 全量榜单。排除了同名 CMS、游戏装扮库、桌面美化及普通服装商城。

## 建议

优先以 Anyesh/wardrowbe 做小规模验证，验证通过后再决定 fork 为 IWardrobe。它已经覆盖家庭邀请、个人衣物隔离、天气/场合推荐、洗涤状态、穿着反馈和 Docker 部署。补充重点是洗标/材质的结构化审核，以及用户希望的衣物标准展示图流程。如果更看重单容器、低维护的衣橱管理，可选择 Libre-Closet，但 AI 推荐需要另行实现。

无 GPU 不妨碍这个产品：NAS 承担数据、网页、任务调度和 CPU 图像预处理；云端承担视觉理解。虚拟试穿和复杂生成式还原作为可选功能。

## 应用候选（按 Stars 降序）

| 仓库 | Stars | 许可 | 最近 push（UTC） | 实际用途和边界 |
| --- | ---: | --- | --- | --- |
| [tandpfun/wardrobe](https://github.com/tandpfun/wardrobe) | 2,223 | MIT | 2026-07-16 | 多衣物检测、生成正面商品图、透明背景、审批、可选上身展示。React/Vite/Node/sharp、本地 JSON/图片。未见 Docker、家庭账户、天气推荐，适合学习图像工作流。 |
| [Anyesh/wardrowbe](https://github.com/Anyesh/wardrowbe) | 772 | MIT | 2026-10-12 | AI 建档、去背景、家庭邀请、天气/场合/偏好推荐、洗涤与穿着记录、反馈学习、中文。Next.js/FastAPI/Postgres/Redis/arq，多架构 Compose；最适合作基座。 |
| [Lazztech/Libre-Closet](https://github.com/Lazztech/Libre-Closet) | 360 | AGPL-3.0 | 2026-10-11 | PWA、衣物和搭配管理、去背景及修边、日历天气、多用户和查看/编辑分享。NestJS/Fastify/HTMX/SQLite、单容器。未见内置 AI 自动识别或天气穿搭引擎。 |
| [zebangeth/ai-closet](https://github.com/zebangeth/ai-closet) | 291 | MIT | 2025-11-10 | Expo 移动客户端、拍照建档与穿搭画布；云后端在 roadmap，不能当完整 NAS 后端。 |
| [wardrobe-hq/wardrobe](https://github.com/wardrobe-hq/wardrobe) | 25 | AGPL-3.0 | 2026-09-05 | Nuxt/Vue、Compose、rembg；天气/日期标签筛选已有套装。无内置身份认证，家庭隔离未证实。 |
| [TracySteel/shimmer-strip](https://github.com/TracySteel/shimmer-strip) | 9 | README 声明 MIT，API 未识别 | 2026-07-05 | React/Express/JSON，天气和颜色规则、洗衣排除、穿着计数、MCP。适合学习规则与工具接口，账户机制不适合作家庭基座。 |
| [jonnykate/ai-closet](https://github.com/jonnykate/ai-closet) | 1 | MIT | 2026-07-16 | Streamlit/Python，天气、结构化模型结果、实际衣物 ID 校验、穿着反馈；单人预建衣橱，上传和账户仍是 roadmap。 |

补充：[Gurshaan-Deol/Hangar](https://github.com/Gurshaan-Deol/Hangar) 为 1 Star、MIT、最近 push 2026-06-04，提供 Next.js/FastAPI、Compose、天气、视觉建档和多模型接口，家庭能力未证实。Seunkola/Virtualrobe（39 Stars）属于 Android/Firebase 方向，但未检测到许可证且强依赖云服务，不列为优先基座。

## 应该学习和补充的功能

### 1. 图像导入：学习 tandpfun，但区分分割和生成

[导入源码](https://github.com/tandpfun/wardrobe/blob/main/scripts/import-job-api.mjs) 包含衣物检测和 bounding box、裁剪、生成空衣服正面图、背景清理、人工重做与审批，分别保存原图和中间产物。

它采用生成式重建。提示词要求保持纹理不等于证明纽扣、图案、衣长和遮挡细节全部真实。对铺在床上、较平整且正面拍摄的衣物，主体分割、旋转裁剪和适当透视修正可得到可靠透明图；对穿在人体上的衣物，单张照片不能保证恢复不可见部分或真实平铺形状。普通去背景也可能把人体作为前景保留。

建议将图片类型明确分为 original、cutout、generated_display、label_material、label_care。原图和分割图用于事实溯源，生成图仅作经过确认的展示图，不覆盖原图，也不用于反推材质和尺寸。

### 2. 家庭、洗衣和推荐：学习 wardrowbe

- [家庭服务](https://github.com/Anyesh/wardrowbe/blob/main/backend/app/services/family_service.py) 实现邀请及 admin/member。
- [衣物服务](https://github.com/Anyesh/wardrowbe/blob/main/backend/app/services/item_service.py) 按 user_id 过滤读写。[推荐服务](https://github.com/Anyesh/wardrowbe/blob/main/backend/app/services/recommendation_service.py) 只取本人可用衣物，并过滤洗涤和禁用状态。
- [推荐提示词](https://github.com/Anyesh/wardrowbe/blob/main/backend/app/prompts/recommendation.txt) 使用体感温度、降雨、场合、颜色、材质和分层信息。
- [学习服务](https://github.com/Anyesh/wardrowbe/blob/main/backend/app/services/learning_service.py) 利用评分、采纳、实际穿着反馈调整偏好和配对分数。它不是为每个家庭重新训练大模型。
- [衣物模型](https://github.com/Anyesh/wardrowbe/blob/main/backend/app/models/item.py) 有 material、附加图片、洗涤状态，但没有完整的纤维比例、护理符号及洗标审核模块。

家庭成员账户不等于“父母一个账户代管无登录儿童档案”；如需后一能力，需增加 person/profile 和管理授权，而不是混用 user_id。家庭隔离还应覆盖图片读取、导出、任务结果和推荐记录；本次没有做全面权限审计。

### 3. 轻量管理与修边：学习 Libre-Closet

[浏览器去背景代码](https://github.com/Lazztech/Libre-Closet/blob/main/public/js/background-removal.js) 在浏览器 Worker 运行 ONNX/WASM/WebGPU，由 NAS 提供模型文件，支持失败回退。它能够把部分计算放到手机或电脑，但实际速度和移动端兼容性仍需验证。

[分享服务](https://github.com/Lazztech/Libre-Closet/blob/main/src/wardrobe-share/wardrobe-share.service.ts) 实现 VIEW/MANAGE 权限。[衣物字段](https://github.com/Lazztech/Libre-Closet/blob/main/src/dal/entity/garment.entity.ts) 的 washingDetails 是文本；其天气能力是日历预报，不应写成已经实现 AI 天气穿搭。

## 图像和检索组件（独立于应用榜单）

| 项目 | Stars | 许可/用途 | 无 GPU 方案 |
| --- | ---: | --- | --- |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 90,994 | Apache-2.0；标签文字提取 | CPU 小模型；洗涤图标还需视觉识别/图标分类和确认。 |
| [rembg](https://github.com/danielgatis/rembg) | 25,045 | 代码 MIT，权重许可独立；去背景服务封装 | 显式选择 u2netp/u2net/BiRefNet lite；单任务队列起步。 |
| [IDM-VTON](https://github.com/yisol/IDM-VTON) | 5,219 | 代码与权重 CC BY-NC-SA 4.0；虚拟试穿 | CUDA 方向，不作为当前 NAS 依赖。 |
| [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) | 4,278 | 代码及所核实官方模型卡 MIT；高质量主体分割 | 轻量版可做 CPU 实测候选，GPU 基准不能当 NAS 性能。 |
| [CatVTON](https://github.com/Zheng-Chong/CatVTON) | 1,869 | 代码、权重和 demo 为 CC BY-NC-SA 4.0；虚拟试穿 | 官方约 8GB 指显存，不是 NAS 内存；留到外部 GPU 阶段。 |
| [FashionCLIP](https://github.com/patrickjohncyh/fashion-clip) | 542 | 代码和模型 MIT；图文检索、相似衣物搜索 | 支持 CPU；可在入库时提取向量。相似度不等于搭配兼容度。 |

当前 rembg 文档默认模型为 bria-rmbg/RMBG-2.0，其权重与包装代码许可不同；应固定库版本和模型，不能只看 MIT。Wardrowbe 自身 Compose 当前显式指定 u2net。本次没有 NAS 性能实测，不承诺耗时或内存。

IDM-VTON/CatVTON 的任务是将衣服试穿到人像上，不是现成的“人体照片反向恢复平铺衣服”。

## 建议的数据与推荐工作流

1. 选择所属家庭成员，分别拍衣物正面、材质标签、护理标签；支持补拍和纠错。
2. NAS 保存原件，处理 EXIF 旋转、尺寸、缩略图、内容哈希；主体分割异步执行。
3. 视觉模型输出类别、颜色、图案、风格等建议；标签提取纤维比例、尺码、护理文字及符号。不能从外观断言真实纤维比例。
4. 每个属性保存来源（标签/视觉估计/用户）、原始证据、待确认状态和模型版本；看不清返回未知，不补造具体值。模型 confidence 不能当校准概率。
5. 用户确认后成为可推荐衣物，支持 ready、needs_wash、washing、stored、archived 等业务状态；这些新增状态属于建议。
6. 每日按出门时段取体感温度、风雨和温差；先过滤所属成员、尺码、洁净状态、场合和可用性，再评分配色、风格、偏好与重复穿着。
7. 给模型有限的真实 item_id 候选，生成约三套方案；程序重新检查 ID、权限、衣物状态、槽位完整性和重复，然后显示原衣物拼贴及解释。
8. 记录“实际穿了”、太冷/太热、喜欢/不喜欢及原因，逐步调整每个成员的偏好。冷启动靠问卷和规则；不需要为少量家庭数据训练大模型。

推荐分数可定义为天气舒适、场合适配、颜色协调、个人偏好、新颖度的加权和，重复穿着为惩罚；权重需从用户反馈调整，不是已验证的时尚定律。先做类别/标签筛选，后续需要自然语言或以图搜衣时再加 FashionCLIP/pgvector。

[Open-Meteo 文档](https://open-meteo.com/en/docs) 提供体感温度、逐时天气、降雨和风等字段；[使用条款](https://open-meteo.com/en/terms) 允许符合限额的非商业家庭用途并要求署名。实现城市/时区设置、缓存、预报时间及断网回退；不要仅用一天平均气温做决策。

## 飞牛 OS 部署技术栈

优先继承 [Wardrowbe 的生产 Compose](https://github.com/Anyesh/wardrowbe/blob/main/docker-compose.prod.yml) 和 [.env.example](https://github.com/Anyesh/wardrowbe/blob/main/.env.example)：

| 层 | 建议选择 | 原因 |
| --- | --- | --- |
| 手机入口 | Next.js/TypeScript 响应式网页；PWA 可增强 | 手机拍照/选图、家人同一服务使用。 |
| API | Python FastAPI + Pydantic | 复用现有业务、结构化校验和图像生态。 |
| 数据 | PostgreSQL + NAS 持久化目录 | 元数据与原图分开；保留稳定图片关联。 |
| 队列 | Redis + arq，AI 和 image worker 分开 | 批量导入、重试、定时任务、隔离 CPU 任务。 |
| 本地图像 | Pillow/OpenCV + rembg/ONNX Runtime CPU | 非生成的旋转、裁剪、透明图和缩略图。 |
| 模型适配 | DeepSeek API 首接；SIWC/OpenAI API 可选 | 无 GPU 时把视觉理解移到云端，保持提供者可更换。 |
| 天气 | Open-Meteo + 缓存 | 获取出门时段天气；提供天气服务接口以便替换。 |
| 登录入口 | OIDC 或可靠 forward-auth + HTTPS 反代 | 家庭成员独立身份；不要沿用默认开发登录。 |
| 运维 | Compose、固定镜像版本、数据卷和数据库备份 | NAS 重启恢复，升级可回滚，定期验证恢复。 |

上游生产 Compose 当前有 Postgres、Redis、API、AI worker、image-worker、Next.js、nginx 七个服务，未要求 GPU，也没有强制内置 Ollama。云端模型要设置 AI_BASE_URL、AI_API_KEY、AI_VISION_MODEL、AI_TEXT_MODEL，AI_INTERNAL_ENABLED 保持 true；false 的含义是禁用内部 AI 而委托外部 agent。OpenAI 兼容并不证明所有供应商参数均可即插即用，仍要验证图像请求和 JSON 输出。

图片存储自托管不等于模型处理全本地。云视觉请求会发送照片给相应提供商；可以先裁剪衣物/标签，减少无关人物和背景。推荐阶段优先发送已确认的结构化元数据，减少重复传图和费用。API 凭据只放后端。

## DeepSeek 与 Codex/ChatGPT 订阅

详见 [模型接入核实](./model-access.md)。关键结论：

- [DeepSeek 当前官方视觉文档](https://api-docs.deepseek.com/zh-cn/guides/vision/) 已明确 deepseek-flash 支持图片输入，适合视觉识别候选；不是图片生成接口。
- [Sign in with ChatGPT](https://developers.openai.com/siwc/quickstart) 支持符合条件的 Plus/Pro 用户为开源或本地个人应用授权使用 plan；[自托管 VM 文档](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms) 提供可参考的 NAS 认证架构。
- 订阅路线不是通用无限 API 额度；需验证账号资格、模型、额度和 OAuth 生命周期。独立家庭成员分别授权或统一走标准 API，是清楚的架构边界；官方资料没有全面确立单人订阅共享给家庭代理的授权结论。
- [SIWC 当前限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) 包含支持图片输入、不支持图像生成；不接受 background 字段不等于不能由 NAS 定时队列自行调用普通流式请求。
- Codex CLI/SDK 可作主人的批处理实验，正式固定流程优先用明确的模型 provider。标准 API Key 走独立计费；图像编辑/生成另外接入支持该能力的服务。

## 验证顺序

第一阶段：部署候选的最小试验，录入两名成员和约二三十件代表衣物，确认照片、账户隔离、状态和备份恢复。检验数据库/图片私有访问，不把本次源码阅读当成权限审计。

第二阶段：做标签 OCR/视觉提取及人工确认，验证白色、深色、花纹、复杂床单背景、反光或皱褶标签的成功率；测 NAS 任务耗时和峰值内存，据此固定 CPU 模型及并发。

第三阶段：按天气生成候选，记录实际穿着和冷暖/喜好反馈，验证模型没有推荐不存在、他人或正在洗涤的衣物；云服务失败时保留已有衣橱功能及规则推荐。

第四阶段：按实际需求加入生成式正面展示图、以图搜衣和虚拟试穿。生成图用原图对照确认，保持可撤销。

当前工作仅完成调研笔记，尚未部署到 NAS、调用付费推理或修改应用代码。
