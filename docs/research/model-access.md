# 家庭衣橱应用的模型接入核实

核实日期：2026-10-13。环境：飞牛 OS NAS，无 GPU。本文为官方文档核实和工程建议，未使用用户凭据执行真实推理；账号资格、实际额度和具体照片的识别质量仍需接入时验证。

## 可以采用的路线

| 路线 | 官方已明确的能力 | 本项目建议 |
| --- | --- | --- |
| DeepSeek API | `deepseek-flash` 接受文字和图片，支持 OpenAI 兼容 Chat Completions 与 Responses API。[图像理解](https://api-docs.deepseek.com/zh-cn/guides/vision/) | 作为首个云端识别/推荐适配器。NAS 无 GPU 不影响远程推理；API Key 只保存在后端。 |
| OpenAI API Key | API 认证按 API 用量计费，和订阅额度是不同路径。[认证](https://learn.chatgpt.com/docs/auth)、[计费](https://learn.chatgpt.com/docs/pricing) | 作为家庭后台的独立付费适配器，按所选模型接入图像理解；若需要生成商品展示图，另接支持图像编辑的 API。 |
| Sign in with ChatGPT（SIWC） | 合资格 Plus/Pro 用户可在支持的应用中授权使用自己的 ChatGPT plan；开源客户端不需要用户提供 API Key。[Quickstart](https://developers.openai.com/siwc/quickstart) | 可选的订阅接入，不应再笼统说“Codex/ChatGPT 订阅不能给自建应用用”。先完成授权和最小推理验证。 |
| Codex CLI/SDK | Codex 支持订阅认证；`codex exec` 可用于脚本和定时任务，支持图片输入；SDK 可集成本地 Codex agent。[认证](https://learn.chatgpt.com/docs/auth)、[CLI 参数](https://learn.chatgpt.com/docs/cli/reference)、[SDK](https://learn.chatgpt.com/docs/codex-sdk) | 适合主人自己的实验和人工审核批处理。固定的衣物识别和推荐任务优先直接接模型接口，减少 agent 运行时和权限管理。 |

## DeepSeek：当前已经支持图像

不要按过去的文本模型印象设计。官方当前指定的视觉模型为 `deepseek-flash`；旧名称 `deepseek-v4-flash-vision-exp` 的请求也转由最新 Flash 承接。Chat Completions 请求使用 `user` 消息，`content` 包含 `text` 和 `image_url` 对象；Responses 则使用 `input_text` 和 `input_image`。图片可用 base64 data URL、公开 HTTPS URL 或 Files API 引用。[官方图像理解文档](https://api-docs.deepseek.com/zh-cn/guides/vision/)

最小结构示意（不是已执行代码）：

```json
{
  "model": "deepseek-flash",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "读取洗标，只输出可见文字；看不清的字段返回 null。"},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
  }]
}
```

建议把衣物全图、材质标签、洗涤标签作为不同资产保存。模型输出附带证据来源和待确认状态；材质百分比和洗涤禁忌以标签文字及人工确认值为准。`null` 比臆测具体成分更合适。无公网图片链接需求时，优先 base64 上传，不必为了识别而公开 NAS 相册。这些是本项目的工程建议。

## SIWC：订阅可用，但必须区分接入范围

官方说明面向开源工具、运行于本地的个人项目以及获选的私有应用；收费或由开发者远程托管给用户的应用需要申请相应接入。单纯的身份登录不等于获得模型调用许可，必须取得 `chatgpt.tokens.use.direct` 等授权 scope。[官方集成教程](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)、[注册与授权](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)

**个人 NAS 并非技术上不可行。** 官方另有自托管 VM 流程：本地浏览器完成 OAuth，再通过安全通道把选定账号的受保护凭据转移到自托管运行环境；该环境具有独立、稳定的 host ID，并负责后续 token 刷新。NAS 上的个人容器可参照这一模式设计，但 NAS 这个产品名、家庭成员共享的具体产品形态并未在这些文档中逐项确认。[自托管 VM 指南](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)

家庭使用应区分两种情况：

- **主人管理家庭衣橱、审核并发起批处理：** 可以先以主人自己的个人工具验证 SIWC；这不是向每个家庭成员发放一套订阅额度。
- **每个成员独立进入应用并请求模型：** 若使用 SIWC，设计成各账号分别授权、分别保存注册和凭据、显示当前消耗哪个账号的额度；没有合资格订阅的成员可走应用自己的 API Key 服务。官方要求隔离不同注册的凭据，未把单个订阅声明为通用多用户配额池。[账号与会话](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)

以上是根据官方身份、注册和额度模型作出的架构建议，不能据此声称“所有家庭代理请求都被官方禁止”或“一个人的订阅已获准为全家任意共享”。要把 NAS 做成远程托管的多人服务时，保留标准 API 路线更稳妥。

## SIWC 图像与后台任务限制

此路线支持所选模型接受的文字、图片和文件输入，但目前不支持图像生成工具，也不支持 Files 上传 API。HTTP 请求必须 `store: false`、`stream: true`；不接受 `background`，也不提供持久的服务端会话历史。每次应带必要上下文。[预览限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

这里的“不支持 `background`”指 Responses API 的该字段，不能推导为“NAS 不可定时运行”。工程上可以由 NAS 队列定时启动普通流式请求，自行等待完成、保存结果、处理超时和重新授权；但本次没有执行真实定时调用。用于 NAS 的推荐工作流应将 OAuth 过期、额度用尽和云端失败作为可重试或待处理状态。

调用应走公开 `https://api.openai.com/v1/responses`，不应使用 ChatGPT 私有 `backend-api` 地址。模型列表需要按当前授权账号查询，不能假设桌面客户端可选模型与自建应用完全一致。[模型与推理](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)

Plus 的五小时额度与其他使用该 plan 的应用共享，并不会因新建衣橱应用增加独立配额；官方说明 Pro 不受该五小时限制，但这不等于所有其他限制消失。token 应存放在受保护的后端运行时，刷新操作要串行化，避免轮换凭据竞争。[账号、凭据与额度](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)

## Codex CLI / SDK 的合理用途

`codex exec` 支持 `--image`、`--output-schema` 和结构化事件输出，可做本人发起的“读取衣物照片及标签，生成待审核 JSON”实验。CLI 订阅登录的存在，与 SDK 能集成应用这两点，并不自动建立一个把主人登录态包装成多人共享推理服务的完整授权结论。官方更直接的自建应用订阅接入契约是 SIWC。[CLI 参数](https://learn.chatgpt.com/docs/cli/reference)、[SDK](https://learn.chatgpt.com/docs/codex-sdk)、[SIWC 概览](https://developers.openai.com/siwc/token-sharing-open-source)

无 GPU 的飞牛 OS 首版建议：NAS 保存原图、处理结果、衣橱元数据和推荐记录；CPU worker 做缩放、裁剪和背景分割；云端视觉模型做标签读取和属性建议；规则层先筛选天气、场景、洁净状态和偏好，再让模型给搭配解释。所有云端调用经统一 provider 接口，先实现 DeepSeek API，再按用户实际资格加入 SIWC/OpenAI API；图像生成作为独立可选能力。这里的推荐属于工程取舍，不是已完成部署或质量测试。
