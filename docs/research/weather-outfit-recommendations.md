# 基于天气的衣橱搭配推荐

核查日期：2026-10-22。本文是实现建议和源码阅读记录；未安装或运行以下项目，未验证推荐质量。本次只新增研究笔记，不修改应用功能。Stars 是 GitHub REST API 本次快照，只代表关注度。

## 建议结论

第一版采用 **可穿条件过滤 → 按穿着槽位组套 → 天气与搭配评分 → 输出三套不同方案 → 反馈调整**。这部分可以在现有 FastAPI 后端用普通 Python 完成，不需要 GPU、模型训练或向量数据库。LLM 后续作为可选的重排与解释模块。

硬条件与喜好分开：账号归属、衣物可用状态、用户明确排除、重复 ID、穿着结构完整性必须校验；保暖、配色、风格、复穿间隔通常参与评分。明确不适用的组合可以排除，但不要把粗糙的“冬季”标签等同于绝对禁用。衣橱不足时说明缺哪类衣物，不虚构补齐。

## GitHub 中可借鉴的实现

| 项目 | Stars | 实际推荐方式 | 可借鉴与限制 |
| --- | ---: | --- | --- |
| [Anyesh/wardrowbe](https://github.com/Anyesh/wardrowbe) | 792 | 可用衣物筛选；多因子单品预排序；LLM 组套；编号、身体槽位和完整性处理 | 最接近现有技术栈。可借鉴分层流程、复穿记录、反馈配对；不是经过验证的通用穿衣算法 |
| [TracySteel/shimmer-strip](https://github.com/TracySteel/shimmer-strip) | 9 | 天气标签、穿着槽位、颜色加权随机选取；重复生成后选颜色分数最高者 | 展示了无需 LLM 的小型规则引擎；不能照搬随机加外套及过滤逻辑 |
| [jonnykate/ai-closet](https://github.com/jonnykate/ai-closet) | 1 | 天气与衣橱进入提示词；结构化 LLM 输出；真实 ID 与必需类别校验；失败修正重试 | 输出校验值得采用；其完整性要求固定 Top + Bottom + Footwear，不覆盖连衣裙等结构 |

元数据来源：[wardrowbe API](https://api.github.com/repos/Anyesh/wardrowbe)、[shimmer-strip API](https://api.github.com/repos/TracySteel/shimmer-strip)、[ai-closet API](https://api.github.com/repos/jonnykate/ai-closet)。下述源码链接固定到本次核查提交。

### wardrowbe：规则预排序与 LLM 结合

- [recommendation_service.py](https://github.com/Anyesh/wardrowbe/blob/bbe090ee64d413f330851f4667fe867fa2ea49ff/backend/app/services/recommendation_service.py#L219-L249) 先限定当前用户、ready、未归档、无需洗涤、已知类别与未排除衣物。这是可用性筛选。
- [item_scorer.py](https://github.com/Anyesh/wardrowbe/blob/bbe090ee64d413f330851f4667fe867fa2ea49ff/backend/app/services/item_scorer.py#L463-L528) 将天气、正式程度、季节、最近穿着、偏好、使用频率相乘，并添加历史搭配奖励、保留必要类别。**少于 50 件时跳过这一预评分**；大衣橱最多传入 70 件。天气等因素在此是排序分数，并非完整的硬约束。
- [recommendation.txt](https://github.com/Anyesh/wardrowbe/blob/bbe090ee64d413f330851f4667fe867fa2ea49ff/backend/app/prompts/recommendation.txt#L48-L64) 要求三套搭配，支持上装+下装、连体服、套装等结构；给出现有编号及颜色、材质、层次等提示。[输出处理](https://github.com/Anyesh/wardrowbe/blob/bbe090ee64d413f330851f4667fe867fa2ea49ff/backend/app/services/recommendation_service.py#L138-L196) 再过滤无效编号、去重身体槽位，必要时补齐缺件。
- [weather_service.py](https://github.com/Anyesh/wardrowbe/blob/bbe090ee64d413f330851f4667fe867fa2ea49ff/backend/app/services/weather_service.py#L289-L389) 使用 Open-Meteo 当前天气、逐时温度/降雨概率、日最高最低温，计算到本地 21 点的温度窗口。其[普通天气评分](https://github.com/Anyesh/wardrowbe/blob/bbe090ee64d413f330851f4667fe867fa2ea49ff/backend/app/services/item_scorer.py#L206-L244) 使用气温/温度范围，体感温度另外进入提示词。因此“读取了体感字段”不等于“规则已按体感计算”。
- [反馈读取](https://github.com/Anyesh/wardrowbe/blob/bbe090ee64d413f330851f4667fe867fa2ea49ff/backend/app/services/recommendation_service.py#L559-L625) 将已计算的颜色/风格偏好，以及至少两次配对且达到阈值的衣物组合带回推荐。这证明了反馈接入路径，不证明推荐质量或个人保暖模型已经有效。

### shimmer-strip：轻量规则路线

[outfitEngine.js](https://github.com/TracySteel/shimmer-strip/blob/2cab8da1d9c1b3347b5a6fef9798ed3f8016975b/src/outfitEngine.js#L17-L245) 将天气分为 Hot/Warm/Mild/Cold/Rainy；按类别构造连体或上下装组合，颜色分数影响抽样概率，外套由天气对应概率决定。[generateBestOutfit](https://github.com/TracySteel/shimmer-strip/blob/2cab8da1d9c1b3347b5a6fef9798ed3f8016975b/src/outfitEngine.js#L330-L342) 默认生成五次后取颜色评分最高者。

阅读可见两个限制：vibe/weather 阶段部分过滤从原始 `items` 重新开始，可能覆盖前一步过滤；外套概率不能保证冷天一定有足够保暖层。[天气服务](https://github.com/TracySteel/shimmer-strip/blob/2cab8da1d9c1b3347b5a6fef9798ed3f8016975b/src/weather-server.js#L23-L101) 今日主要用当前气温、明日用最高最低均值进行分段，未针对实际外出时段评分。适合参考模块边界，不宜复制其阈值作为普遍规律。

### ai-closet：LLM 输出也必须由程序校验

[prompt_builder.py](https://github.com/jonnykate/ai-closet/blob/92d035260925bc2449862fd8798d0f7b51b98c63/src/prompt_builder.py#L21-L64) 提供真实衣橱、天气、最近单品/组合和反馈，要求只使用现有 ID。[llm_client.py](https://github.com/jonnykate/ai-closet/blob/92d035260925bc2449862fd8798d0f7b51b98c63/src/llm_client.py#L43-L119) 使用 Pydantic 结构化输出，校验 ID 存在、无重复、必需类别齐全，最多两次生成尝试。

[history.py](https://github.com/jonnykate/ai-closet/blob/92d035260925bc2449862fd8798d0f7b51b98c63/src/history.py#L40-L118) 保存评分和是否穿过，再把近期反馈写回提示词。这是轻量上下文反馈，不能称为已训练的个性化推荐模型。完整性校验只覆盖上装+下装+鞋，天气适配与不重复整套等提示词要求并未都变成程序硬约束。

## IWardrobe 的最小实现方向（工程建议）

### 1. 天气按用户外出时间处理

输入城市/位置、日期、外出起止时间、场合，以及可选的主要在室内/户外。使用当地时区，对该时段逐时的体感最低/最高温、降水概率与降水量、风速/阵风作摘要；早晚冷、中午热时优先可脱外层，避免仅看全天平均温度。

[Open-Meteo 官方文档](https://open-meteo.com/en/docs) 提供上述逐时字段，并将体感温度定义为结合风寒、湿度与太阳辐射的指标。若已经使用它，建议不要再机械重复扣减风寒；风仍可影响防风层与户外活动适配。先缓存天气、标明地点和更新时间；请求失败时允许使用明确标注的近期缓存或手动天气，不把默认晴天当实时结果。[使用条款](https://open-meteo.com/en/terms) 对免费非商业 API、署名及服务保证有说明。

### 2. 先补少量衣物属性

现有类别、颜色、季节、材质、可用状态、收藏、穿着记录可以开始评分，但不足以区分薄羊毛衫与厚羊毛大衣。建议优先补：

- 保暖等级：薄/中/厚，允许未知；作为可调整的经验标签，不伪装成精确 clo。
- 穿着位置：内搭/中层/外层；袖长/裤长；连体衣物覆盖哪些槽位。
- 场合与风格：少量可多选标签。
- 防风、防雨：有证据或用户确认才标记，不能根据照片和“夹克”类别直接断定。

照片识别可提出初值，用户可改；不确定字段保留未知。BiRefNet Lite 只处理前景，不负责保暖或材质判断。

### 3. 生成真正完整的候选组合

按“上装+下装+鞋”或“连体衣物+鞋”组套，再根据天气考虑中层、外层和配饰。先保留每个必需槽位的一小批合适衣物，再有限枚举/逐步保留高分组合，避免把全衣橱任意排列。

对整套而非仅对单品评分：天气舒适度、场合一致性、颜色/款式协调、用户偏好、近期复穿。各项有界且可解释；缺鞋/冷天无合适外套时返回缺项说明。最终三套尽量更换关键单品，避免只是同一套换个配饰。

### 4. LLM 可选，候选边界由后端保证

规则产生少量完整候选，并赋予 `candidate_id`。可选 LLM 仅返回候选排序、简短原因与调整建议；后端验证 ID，模型异常或超时时返回规则结果。先使用结构化属性，不必每天重传所有原图。

这样的边界是本项目建议，比让 LLM 自由选择任意衣物更容易验证。后续确需让它重组单品时，再校验真实归属、可用状态、完整槽位和天气条件；仅“返回 JSON”不足以保证正确。

[FashionCLIP](https://github.com/patrickjohncyh/fashion-clip/blob/master/README.md) 的公开用途包括图文向量、检索与零样本分类。它可辅助找相似衣物和风格标签，但“相似度”不能直接视作“上下装搭配兼容度”，也不是开箱即用的天气整套推荐器。第一版无需因此增加向量数据库。

### 5. 反馈先做可理解的小幅调整

记录“采用/实际穿了/喜欢/不喜欢/偏冷/偏热/替换了哪件”，关联当时天气、出行场景、完整搭配和算法版本。喜欢与冷热反馈分开：一套太冷不应自动学成讨厌它的颜色；未点击也不应直接计为不喜欢。先平滑调整个人冷热偏移和颜色/风格权重，保留复穿间隔、允许少量多样性，再用真实使用结果决定是否引入学习排序。

实现顺序建议：天气上下文与少量标签 → 本地规则三套推荐及理由 → 采用/冷热反馈闭环 → 按实际不足决定是否加入 LLM 重排。现有 Postgres 保存推荐快照和反馈，Redis 缓存天气；只有调用外部模型等耗时环节才需要复用 arq 后台队列。
